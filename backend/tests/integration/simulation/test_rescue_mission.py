import json
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    get_stock,
    make_combined_routing_llm,
    make_entity_routing_llm,
)

pytestmark = pytest.mark.asyncio


_BROKEN_CARGO = {
    "material_id": "cimento",
    "quantity_tons": 50.0,
    "origin_type": "warehouse",
    "origin_id": "warehouse-002",
    "destination_type": "store",
    "destination_id": "store-001",
}


async def _setup_broken_truck_with_cargo(session):
    route_id = uuid4()
    order_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO pending_orders "
            "(id, requester_type, requester_id, target_type, target_id, material_id, quantity_tons, status, age_ticks) "
            "VALUES (:oid, 'store', 'store-001', 'warehouse', 'warehouse-002', 'cimento', 50.0, 'confirmed', 0)"
        ),
        {"oid": order_id},
    )
    await session.execute(
        text(
            "INSERT INTO routes (id, truck_id, origin_type, origin_id, dest_type, dest_id, "
            "path, timestamps, eta_ticks, status, order_id, started_at) "
            "VALUES (:rid, 'truck-006', 'warehouse', 'warehouse-002', 'store', 'store-001', "
            "CAST(:path AS jsonb), CAST(:ts AS jsonb), 5, 'active', :oid, NOW())"
        ),
        {
            "rid": route_id,
            "path": json.dumps([[-46.6, -23.5], [-46.5, -23.5]]),
            "ts": json.dumps([0, 10]),
            "oid": order_id,
        },
    )
    await session.execute(
        text(
            "UPDATE trucks SET status='broken', degradation=0.85, breakdown_risk=0.6, "
            "cargo=CAST(:cargo AS jsonb), active_route_id=:rid WHERE id='truck-006'"
        ),
        {"cargo": json.dumps(_BROKEN_CARGO), "rid": route_id},
    )
    await session.execute(
        text(
            "INSERT INTO events (id, event_type, source, entity_type, entity_id, payload, status, tick_start) "
            "VALUES (gen_random_uuid(), 'truck_breakdown', 'engine', 'truck', 'truck-006', CAST(:payload AS jsonb), 'active', 0)"
        ),
        {"payload": json.dumps({"reason": "mid-route breakdown"})},
    )
    await session.commit()
    return str(route_id), str(order_id)


async def _fetch_rescue_event(session, broken_truck_id: str):
    result = await session.execute(
        text(
            "SELECT entity_id, payload::text AS payload FROM events "
            "WHERE event_type='contract_proposal' AND entity_type='truck' "
            "AND payload->>'rescue_for' = :bid "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"bid": broken_truck_id},
    )
    return result.first()


async def test_alert_breakdown_dispatches_rescue_event(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_broken_truck_with_cargo(session)

    alert_response = {
        "action": "alert_breakdown",
        "payload": {"current_degradation": 0.85},
        "reasoning_summary": "Reporting breakdown",
    }
    llm = make_entity_routing_llm(**{"truck-006": [alert_response]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    rescue = await _fetch_rescue_event(session, "truck-006")
    assert rescue is not None, "Expected a contract_proposal with rescue_for payload"
    assert rescue.entity_id != "truck-006"

    payload = json.loads(rescue.payload)
    assert payload.get("rescue_for") == "truck-006"
    assert payload.get("material_id") == "cimento"
    assert float(payload.get("quantity_tons")) == 50.0
    assert payload.get("destination_id") == "store-001"
    assert payload.get("destination_type") == "store"


async def test_rescue_truck_accepts_and_delivers(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    _, order_id = await _setup_broken_truck_with_cargo(session)

    initial_store_stock = await get_stock(
        session, "store_stocks", "store_id", "store-001", "cimento"
    )

    alert_response = {
        "action": "alert_breakdown",
        "payload": {"current_degradation": 0.85},
        "reasoning_summary": "Reporting breakdown",
    }
    llm_t1 = make_entity_routing_llm(**{"truck-006": [alert_response]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    rescue = await _fetch_rescue_event(session, "truck-006")
    assert rescue is not None
    rescue_truck_id = rescue.entity_id

    accept_response = {
        "action": "accept_contract",
        "payload": {"order_id": order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accepting rescue",
    }
    llm_t2 = make_combined_routing_llm(by_agent={"truck": [accept_response]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t2):
        await advance_ticks_with_settle(client, 1)

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 6)

    await session.rollback()
    rescue_status = await session.execute(
        text("SELECT status FROM trucks WHERE id=:tid"),
        {"tid": rescue_truck_id},
    )
    assert rescue_status.scalar_one() == "idle"

    final_store_stock = await get_stock(
        session, "store_stocks", "store_id", "store-001", "cimento"
    )
    assert float(final_store_stock) > float(initial_store_stock)


async def test_rescue_preserves_destination(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    _, order_id = await _setup_broken_truck_with_cargo(session)

    initial_store_stock = await get_stock(
        session, "store_stocks", "store_id", "store-001", "cimento"
    )
    initial_warehouse_stock = await get_stock(
        session, "warehouse_stocks", "warehouse_id", "warehouse-002", "cimento"
    )

    alert_response = {
        "action": "alert_breakdown",
        "payload": {"current_degradation": 0.85},
        "reasoning_summary": "Reporting breakdown",
    }
    llm_t1 = make_entity_routing_llm(**{"truck-006": [alert_response]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    rescue = await _fetch_rescue_event(session, "truck-006")
    assert rescue is not None

    accept_response = {
        "action": "accept_contract",
        "payload": {"order_id": order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accepting rescue",
    }
    llm_t2 = make_combined_routing_llm(by_agent={"truck": [accept_response]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t2):
        await advance_ticks_with_settle(client, 1)

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 6)

    await session.rollback()
    final_store_stock = await get_stock(
        session, "store_stocks", "store_id", "store-001", "cimento"
    )
    final_warehouse_stock = await get_stock(
        session, "warehouse_stocks", "warehouse_id", "warehouse-002", "cimento"
    )

    assert float(final_store_stock) > float(initial_store_stock)
    assert float(final_warehouse_stock) <= float(initial_warehouse_stock)
