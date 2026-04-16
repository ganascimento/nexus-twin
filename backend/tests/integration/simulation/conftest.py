import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
from httpx import ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.main import app
from src.database.session import get_db
from src.database.seed import seed_default_world
from src.services.simulation import SimulationService
from src.simulation.engine import SimulationEngine


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

    app.dependency_overrides.clear()
    if original_state is not None:
        app.state.simulation_service = original_state


_TABLES_TO_TRUNCATE = [
    "agent_decisions", "pending_orders", "events",
    "store_stocks", "warehouse_stocks", "factory_products", "factory_partner_warehouses",
    "trucks", "routes", "stores", "warehouses", "factories", "materials",
]


@pytest.fixture
async def seeded_simulation_client(async_engine, mock_redis):
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)

    async with session_factory() as cleanup_session:
        for table in _TABLES_TO_TRUNCATE:
            await cleanup_session.execute(text(f"DELETE FROM {table}"))
        await cleanup_session.commit()

    async with session_factory() as seed_session:
        await seed_default_world(seed_session)
        await seed_session.commit()

    engine = SimulationEngine(mock_redis, session_factory)
    sim_service = SimulationService(engine)

    async with session_factory() as test_session:
        async def _override_get_db():
            yield test_session

        app.dependency_overrides[get_db] = _override_get_db
        original_state = getattr(app.state, "simulation_service", None)
        app.state.simulation_service = sim_service

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test/api/v1"
        ) as c:
            yield c, test_session, mock_redis

        app.dependency_overrides.clear()
        if original_state is not None:
            app.state.simulation_service = original_state


async def advance_n_ticks(client, n: int) -> list[dict]:
    results = []
    for _ in range(n):
        resp = await client.post("/simulation/tick")
        results.append(resp.json())
    return results
