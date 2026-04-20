import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
from httpx import ASGITransport
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.main import app
from src.database.session import get_db
from src.database.seed import seed_default_world
from src.services.simulation import SimulationService
from src.simulation.engine import SimulationEngine


AGENT_SETTLE_TIME = 0.5

VALHALLA_MOCK_ROUTE = {
    "path": [[-46.6, -23.5], [-46.7, -23.4], [-46.8, -23.3], [-46.9, -23.2], [-47.0, -23.1]],
    "timestamps": [0, 1, 2, 3, 4],
    "distance_km": 100.0,
    "eta_ticks": 3,
}


def make_llm_responses(*response_dicts):
    return FakeMessagesListChatModel(
        responses=[AIMessage(content=json.dumps(r)) for r in response_dicts]
    )


_AGENT_KEYWORDS = {
    "Fábrica": "factory",
    "Armazém": "warehouse",
    "Loja": "store",
    "Caminhão": "truck",
}

_DEFAULT_HOLD_RESPONSE = {"action": "hold", "payload": None, "reasoning_summary": "no-op"}


class RoutingFakeLLM:
    def __init__(
        self,
        responses_by_agent: dict[str, list[dict]] | None = None,
        responses_by_entity: dict[str, list[dict]] | None = None,
    ):
        self._agent_queues = {
            k: [AIMessage(content=json.dumps(r)) for r in v]
            for k, v in (responses_by_agent or {}).items()
        }
        self._entity_queues = {
            k: [AIMessage(content=json.dumps(r)) for r in v]
            for k, v in (responses_by_entity or {}).items()
        }

    def bind_tools(self, tools):
        return self

    def _detect_agent_type(self, messages) -> str | None:
        for msg in messages:
            content = getattr(msg, "content", "") or ""
            for keyword, agent_type in _AGENT_KEYWORDS.items():
                if keyword in content:
                    return agent_type
        return None

    def _detect_entity_id(self, messages) -> str | None:
        for msg in messages:
            content = getattr(msg, "content", "") or ""
            for entity_id in self._entity_queues:
                if f"`{entity_id}`" in content or f" {entity_id} " in content:
                    return entity_id
        return None

    def _pick_response(self, messages):
        entity_id = self._detect_entity_id(messages)
        if entity_id and self._entity_queues.get(entity_id):
            return self._entity_queues[entity_id].pop(0)
        agent_type = self._detect_agent_type(messages)
        if agent_type and self._agent_queues.get(agent_type):
            return self._agent_queues[agent_type].pop(0)
        return AIMessage(content=json.dumps(_DEFAULT_HOLD_RESPONSE))

    async def ainvoke(self, messages, *args, **kwargs):
        return self._pick_response(messages)

    def invoke(self, messages, *args, **kwargs):
        return self._pick_response(messages)


def make_routing_llm(**responses_by_agent):
    return RoutingFakeLLM(responses_by_agent=responses_by_agent)


def make_entity_routing_llm(**responses_by_entity):
    return RoutingFakeLLM(responses_by_entity=responses_by_entity)


def make_combined_routing_llm(by_entity=None, by_agent=None):
    return RoutingFakeLLM(
        responses_by_agent=by_agent or {},
        responses_by_entity=by_entity or {},
    )


async def advance_ticks_with_settle(client, n: int, settle_time: float = AGENT_SETTLE_TIME, inter: float = 0.1):
    service = getattr(app.state, "simulation_service", None)
    engine = getattr(service, "_engine", None) if service is not None else None
    for _ in range(n):
        await client.post("/simulation/tick")
        await asyncio.sleep(inter)
        if engine is not None:
            await engine.drain_pending_agents()
    await asyncio.sleep(settle_time)
    if engine is not None:
        await engine.drain_pending_agents()


async def get_order_status(session, order_id) -> str | None:
    result = await session.execute(
        text("SELECT status FROM pending_orders WHERE id = :id"),
        {"id": str(order_id)},
    )
    return result.scalar_one_or_none()


async def get_truck_status(session, truck_id) -> str | None:
    result = await session.execute(
        text("SELECT status FROM trucks WHERE id = :id"),
        {"id": truck_id},
    )
    return result.scalar_one_or_none()


async def get_stock(session, table: str, entity_col: str, entity_id: str, material_id: str) -> float | None:
    result = await session.execute(
        text(f"SELECT stock FROM {table} WHERE {entity_col} = :eid AND material_id = :mid"),
        {"eid": entity_id, "mid": material_id},
    )
    return result.scalar_one_or_none()


async def get_stock_reserved(session, warehouse_id: str, material_id: str) -> float | None:
    result = await session.execute(
        text("SELECT stock_reserved FROM warehouse_stocks WHERE warehouse_id = :wid AND material_id = :mid"),
        {"wid": warehouse_id, "mid": material_id},
    )
    return result.scalar_one_or_none()


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    redis.aclose = AsyncMock()
    pubsub = AsyncMock()
    pubsub.subscribe = AsyncMock()
    pubsub.get_message = AsyncMock(return_value=None)
    pubsub.unsubscribe = AsyncMock()
    pubsub.close = AsyncMock()
    redis.pubsub.return_value = pubsub
    return redis


@pytest.fixture
async def simulation_client(async_engine, async_session, mock_redis):
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)

    engine = SimulationEngine(mock_redis, session_factory)
    sim_service = SimulationService(engine)

    async def _override_get_db():
        yield async_session

    app.dependency_overrides[get_db] = _override_get_db
    original_state = getattr(app.state, "simulation_service", None)
    app.state.simulation_service = sim_service

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test/api/v1"
    ) as c:
        yield c

    await engine.drain_pending_agents(timeout=5.0)
    app.dependency_overrides.clear()
    if original_state is not None:
        app.state.simulation_service = original_state


_TABLES_TO_TRUNCATE = [
    "agent_decisions", "pending_orders", "events",
    "store_stocks", "warehouse_stocks", "factory_products", "factory_partner_warehouses",
    "trucks", "routes", "stores", "warehouses", "factories", "materials",
]


class RefreshingSession:
    def __init__(self, session_factory):
        self._factory = session_factory
        self._session = None

    async def _ensure(self):
        if self._session is None:
            self._session = self._factory()
            await self._session.__aenter__()
        return self._session

    async def _reset(self):
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None

    async def execute(self, *args, **kwargs):
        s = await self._ensure()
        return await s.execute(*args, **kwargs)

    async def commit(self):
        if self._session is not None:
            await self._session.commit()
            await self._reset()

    async def rollback(self):
        if self._session is not None:
            await self._session.rollback()
            await self._reset()

    async def close(self):
        await self._reset()


@pytest.fixture
async def seeded_simulation_client(async_engine, mock_redis):
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)

    async with session_factory() as cleanup_session:
        await cleanup_session.execute(
            text("TRUNCATE TABLE " + ", ".join(_TABLES_TO_TRUNCATE) + " RESTART IDENTITY CASCADE")
        )
        await cleanup_session.commit()

    async with session_factory() as seed_session:
        await seed_default_world(seed_session)
        await seed_session.commit()

    engine = SimulationEngine(mock_redis, session_factory)
    sim_service = SimulationService(engine)

    async def _override_get_db():
        async with session_factory() as api_session:
            try:
                yield api_session
                await api_session.commit()
            except Exception:
                await api_session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    original_state = getattr(app.state, "simulation_service", None)
    app.state.simulation_service = sim_service

    test_session = RefreshingSession(session_factory)
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test/api/v1"
        ) as c:
            yield c, test_session, mock_redis
    finally:
        await engine.drain_pending_agents()
        await test_session.close()
        app.dependency_overrides.clear()
        if original_state is not None:
            app.state.simulation_service = original_state


async def advance_n_ticks(client, n: int) -> list[dict]:
    results = []
    for _ in range(n):
        resp = await client.post("/simulation/tick")
        results.append(resp.json())
    return results


@pytest.fixture
def mock_valhalla():
    with patch(
        "src.services.route.RouteService.compute_route",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = VALHALLA_MOCK_ROUTE
        yield mock


@pytest.fixture(autouse=True)
def no_random_breakdown(request):
    if "allow_random_breakdown" in request.keywords:
        yield
        return
    with patch("src.simulation.engine.roll_breakdown", return_value=False):
        yield


class _NoOpenAIStub:
    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages, *args, **kwargs):
        raise RuntimeError(
            "Integration test invoked ChatOpenAI without an explicit mock. "
            "Use `with patch('src.agents.base.ChatOpenAI', return_value=<fake>)` "
            "inside the test."
        )

    def invoke(self, messages, *args, **kwargs):
        raise RuntimeError("unmocked ChatOpenAI.invoke")


@pytest.fixture(autouse=True)
def _block_real_openai_calls():
    with patch("src.agents.base.ChatOpenAI", return_value=_NoOpenAIStub()):
        yield
