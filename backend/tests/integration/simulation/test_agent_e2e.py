import asyncio
import json
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from sqlalchemy import text

pytestmark = pytest.mark.asyncio

AGENT_SETTLE_TIME = 2.0


def _fake_llm(response_json: str) -> FakeMessagesListChatModel:
    return FakeMessagesListChatModel(
        responses=[AIMessage(content=response_json)]
    )


# ---------------------------------------------------------------------------
# Scenario 1 — Store agent creates order on low stock
# ---------------------------------------------------------------------------


async def test_store_agent_creates_order_on_low_stock(seeded_simulation_client):
    client, session, mock_redis = seeded_simulation_client

    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
    await session.commit()

    llm = _fake_llm(json.dumps({
        "action": "order_replenishment",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 30.0,
            "from_warehouse_id": "warehouse-002",
        },
        "reasoning_summary": "Stock below reorder point",
    }))

    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        resp = await client.post("/simulation/tick")
        assert resp.status_code == 200
        await asyncio.sleep(AGENT_SETTLE_TIME)

    await session.rollback()

    result = await session.execute(
        text("SELECT action FROM agent_decisions WHERE entity_id='store-001' ORDER BY created_at DESC LIMIT 1")
    )
    decision = result.scalar_one_or_none()
    assert decision == "order_replenishment"


async def test_store_agent_decision_payload_contains_order_details(seeded_simulation_client):
    client, session, mock_redis = seeded_simulation_client

    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
    await session.commit()

    llm = _fake_llm(json.dumps({
        "action": "order_replenishment",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 30.0,
            "from_warehouse_id": "warehouse-002",
        },
        "reasoning_summary": "Requesting resupply",
    }))

    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await client.post("/simulation/tick")
        await asyncio.sleep(AGENT_SETTLE_TIME)

    await session.rollback()

    result = await session.execute(
        text("SELECT payload::text FROM agent_decisions WHERE entity_id='store-001' AND action='order_replenishment' ORDER BY created_at DESC LIMIT 1")
    )
    payload_text = result.scalar_one_or_none()
    assert payload_text is not None
    import json as json_mod
    payload = json_mod.loads(payload_text)
    assert payload["material_id"] == "cimento"
    assert payload["quantity_tons"] == 30.0


# ---------------------------------------------------------------------------
# Scenario 2 — Warehouse agent creates resupply order
# ---------------------------------------------------------------------------


async def test_warehouse_agent_creates_resupply_on_low_stock(seeded_simulation_client):
    client, session, mock_redis = seeded_simulation_client

    await session.execute(
        text("UPDATE warehouse_stocks SET stock=5.0 WHERE warehouse_id='warehouse-001' AND material_id='vergalhao'")
    )
    await session.commit()

    llm = _fake_llm(json.dumps({
        "action": "request_resupply",
        "payload": {
            "material_id": "vergalhao",
            "quantity_tons": 200.0,
            "from_factory_id": "factory-002",
        },
        "reasoning_summary": "Stock critically low",
    }))

    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await client.post("/simulation/tick")
        await asyncio.sleep(AGENT_SETTLE_TIME)

    await session.rollback()

    result = await session.execute(
        text("SELECT action FROM agent_decisions WHERE entity_id='warehouse-001' ORDER BY created_at DESC LIMIT 1")
    )
    decision = result.scalar_one_or_none()
    assert decision == "request_resupply"


# ---------------------------------------------------------------------------
# Scenario 3 — Factory agent starts production
# ---------------------------------------------------------------------------


async def test_factory_agent_starts_production(seeded_simulation_client):
    client, session, mock_redis = seeded_simulation_client

    await session.execute(
        text(
            "UPDATE factory_products SET stock=50, production_rate_current=0 "
            "WHERE factory_id='factory-003' AND material_id='cimento'"
        )
    )
    await session.commit()

    llm = _fake_llm(json.dumps({
        "action": "start_production",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 25.0,
        },
        "reasoning_summary": "Urgent resupply needed",
    }))

    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await client.post("/simulation/tick")
        await asyncio.sleep(AGENT_SETTLE_TIME)

    await session.rollback()

    result = await session.execute(
        text("SELECT action FROM agent_decisions WHERE entity_id='factory-003' ORDER BY created_at DESC LIMIT 1")
    )
    decision = result.scalar_one_or_none()
    assert decision == "start_production"


# ---------------------------------------------------------------------------
# Scenario 4 — Guardrail rejects invalid LLM response
# ---------------------------------------------------------------------------


async def test_guardrail_rejects_invalid_action(seeded_simulation_client):
    client, session, mock_redis = seeded_simulation_client

    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
    await session.commit()

    llm = _fake_llm(json.dumps({
        "action": "fly_to_moon",
        "payload": {},
        "reasoning_summary": "Invalid action",
    }))

    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        resp = await client.post("/simulation/tick")
        assert resp.status_code == 200
        await asyncio.sleep(AGENT_SETTLE_TIME)

    await session.rollback()

    result = await session.execute(
        text("SELECT COUNT(*) FROM agent_decisions WHERE entity_id='store-001'")
    )
    assert result.scalar() == 0, (
        "Guardrail must prevent ANY decision from being persisted when action is invalid"
    )

    stock_result = await session.execute(
        text("SELECT stock FROM store_stocks WHERE store_id='store-001' AND material_id='cimento'")
    )
    stock = stock_result.scalar_one()
    assert stock < 1.0, "Physics must still run despite guardrail rejection"


# ---------------------------------------------------------------------------
# Scenario 5 — Multi-tick until trigger fires
# ---------------------------------------------------------------------------


async def test_multi_tick_triggers_store_agent(seeded_simulation_client):
    client, session, mock_redis = seeded_simulation_client

    llm = _fake_llm(json.dumps({
        "action": "order_replenishment",
        "payload": {
            "material_id": "tijolos",
            "quantity_tons": 5.0,
            "from_warehouse_id": "warehouse-002",
        },
        "reasoning_summary": "Stock depleted over time",
    }))

    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        for _ in range(5):
            await client.post("/simulation/tick")
            await asyncio.sleep(0.5)

    await asyncio.sleep(AGENT_SETTLE_TIME)
    await session.rollback()

    result = await session.execute(
        text("SELECT COUNT(*) FROM agent_decisions WHERE entity_id LIKE 'store-%'")
    )
    assert result.scalar() >= 1


# ---------------------------------------------------------------------------
# Scenario 6 — Engine resilient to agent errors
# ---------------------------------------------------------------------------


async def test_tick_resilient_to_agent_errors(seeded_simulation_client):
    client, session, mock_redis = seeded_simulation_client

    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
    await session.commit()

    broken_llm = MagicMock()
    broken_llm.bind_tools = MagicMock(return_value=broken_llm)
    broken_llm.ainvoke = AsyncMock(side_effect=Exception("LLM is broken"))

    with patch("src.agents.base.ChatOpenAI", return_value=broken_llm):
        resp = await client.post("/simulation/tick")
        assert resp.status_code == 200
        await asyncio.sleep(AGENT_SETTLE_TIME)

    await session.rollback()

    result = await session.execute(
        text("SELECT stock FROM store_stocks WHERE store_id='store-001' AND material_id='cimento'")
    )
    stock = result.scalar_one()
    assert stock < 1.0, "Physics must still execute despite broken LLM"

    decision_count = (await session.execute(
        text("SELECT COUNT(*) FROM agent_decisions WHERE entity_id='store-001'")
    )).scalar()
    assert decision_count == 0, "Broken LLM must not produce any persisted decision"

    status = await client.get("/simulation/status")
    assert status.json()["current_tick"] == 1, "Tick counter must advance despite agent failure"


# ---------------------------------------------------------------------------
# Scenario 7 — Redis receives agent decision publish
# ---------------------------------------------------------------------------


async def test_redis_receives_agent_decision(seeded_simulation_client):
    client, session, mock_redis = seeded_simulation_client

    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
    await session.commit()

    llm = _fake_llm(json.dumps({
        "action": "order_replenishment",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 30.0,
            "from_warehouse_id": "warehouse-002",
        },
        "reasoning_summary": "Low stock",
    }))

    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await client.post("/simulation/tick")
        await asyncio.sleep(AGENT_SETTLE_TIME)

    agent_decision_calls = [
        call for call in mock_redis.publish.call_args_list
        if "agent_decisions" in str(call)
    ]
    assert len(agent_decision_calls) >= 1


# ---------------------------------------------------------------------------
# Scenario 8 — World state published every tick
# ---------------------------------------------------------------------------


async def test_world_state_published_with_agent_running(seeded_simulation_client):
    client, session, mock_redis = seeded_simulation_client

    llm = _fake_llm(json.dumps({
        "action": "hold",
        "payload": None,
        "reasoning_summary": "All good",
    }))

    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await client.post("/simulation/tick")

    world_state_calls = [
        call for call in mock_redis.publish.call_args_list
        if "world_state" in str(call)
    ]
    assert len(world_state_calls) >= 1
