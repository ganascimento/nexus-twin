import json
from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    make_combined_routing_llm,
    make_entity_routing_llm,
)

pytestmark = pytest.mark.asyncio


STORE_ORDER_CIMENTO = {
    "action": "order_replenishment",
    "payload": {
        "material_id": "cimento",
        "quantity_tons": 30.0,
        "from_warehouse_id": "warehouse-002",
    },
    "reasoning_summary": "Low",
}

WAREHOUSE_REQUEST_CIMENTO = {
    "action": "request_resupply",
    "payload": {
        "material_id": "cimento",
        "quantity_tons": 100.0,
        "from_factory_id": "factory-003",
    },
    "reasoning_summary": "Empty",
}

FACTORY_SEND_CIMENTO = {
    "action": "send_stock",
    "payload": {
        "material_id": "cimento",
        "quantity_tons": 100.0,
        "destination_warehouse_id": "warehouse-002",
    },
    "reasoning_summary": "Send",
}

HOLD = {"action": "hold", "payload": None, "reasoning_summary": "no-op"}


async def _stabilize_other_stores(session, store_id: str, skip_material: str):
    await session.execute(
        text(
            "UPDATE store_stocks SET stock=1000 "
            "WHERE store_id=:sid AND material_id != :skip"
        ),
        {"sid": store_id, "skip": skip_material},
    )


async def _setup_store_low_cimento(session):
    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
    await _stabilize_other_stores(session, "store-001", "cimento")
    await session.commit()


async def _setup_empty_warehouse(session):
    await session.execute(
        text("UPDATE warehouse_stocks SET stock=0, stock_reserved=0 WHERE warehouse_id='warehouse-002' AND material_id='cimento'")
    )
    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
    await _stabilize_other_stores(session, "store-001", "cimento")
    await session.commit()


async def _fetch_latest_order_id(session, requester_id: str, material_id: str, target_id: str | None = None):
    where = "requester_id=:rid AND material_id=:mid"
    params = {"rid": requester_id, "mid": material_id}
    if target_id is not None:
        where += " AND target_id=:tid"
        params["tid"] = target_id
    result = await session.execute(
        text(f"SELECT id FROM pending_orders WHERE {where} ORDER BY created_at DESC LIMIT 1"),
        params,
    )
    row = result.first()
    return str(row.id) if row is not None else None


async def _drive_store_delivery(client, session):
    await _setup_store_low_cimento(session)

    llm_t1 = make_entity_routing_llm(**{"store-001": [STORE_ORDER_CIMENTO]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
        await advance_ticks_with_settle(client, 1)

    order_id = await _fetch_latest_order_id(session, "store-001", "cimento")
    assert order_id is not None

    warehouse_confirm = {
        "action": "confirm_order",
        "payload": {"order_id": order_id, "quantity_tons": 30.0, "eta_ticks": 3},
        "reasoning_summary": "Confirm",
    }
    llm_t2 = make_entity_routing_llm(**{"warehouse-002": [warehouse_confirm]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t2):
        await advance_ticks_with_settle(client, 1)

    truck_accept = {
        "action": "accept_contract",
        "payload": {"order_id": order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accept",
    }
    llm_t3 = make_combined_routing_llm(by_agent={"truck": [truck_accept]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t3):
        await advance_ticks_with_settle(client, 1)

    return order_id


async def _drive_warehouse_delivery(client, session):
    await _setup_empty_warehouse(session)

    llm_t1 = make_entity_routing_llm(**{"warehouse-002": [WAREHOUSE_REQUEST_CIMENTO]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
        await advance_ticks_with_settle(client, 1)

    llm_t2 = make_entity_routing_llm(**{"factory-003": [FACTORY_SEND_CIMENTO]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t2):
        await advance_ticks_with_settle(client, 1)

    order_id = await _fetch_latest_order_id(session, "warehouse-002", "cimento", "factory-003")
    assert order_id is not None

    truck_accept = {
        "action": "accept_contract",
        "payload": {"order_id": order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accept",
    }
    llm_t3 = make_combined_routing_llm(by_agent={"truck": [truck_accept]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t3):
        await advance_ticks_with_settle(client, 1)

    return order_id


async def _advance_until_delivered(client, ticks: int = 6):
    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, ticks)


async def test_resupply_delivered_event_created_on_warehouse_arrival(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _drive_warehouse_delivery(client, session)
    await _advance_until_delivered(client, 6)

    await session.rollback()
    rows = (await session.execute(
        text(
            "SELECT entity_type, entity_id FROM events "
            "WHERE event_type='resupply_delivered' AND entity_id='warehouse-002'"
        )
    )).all()
    assert len(rows) >= 1, "resupply_delivered event must be created when truck arrives at warehouse"
    assert rows[0].entity_type == "warehouse"


async def test_resupply_delivered_triggers_warehouse_agent_next_tick(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _drive_warehouse_delivery(client, session)

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 6)

    await session.rollback()
    rows = (await session.execute(
        text(
            "SELECT COUNT(*) FROM agent_decisions "
            "WHERE entity_id='warehouse-002' AND event_type='resupply_delivered'"
        )
    )).all()
    assert int(rows[0][0]) >= 1, (
        "Warehouse agent must receive resupply_delivered event and register a decision"
    )


async def test_resupply_delivered_triggers_store_agent_next_tick(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _drive_store_delivery(client, session)

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 6)

    await session.rollback()
    rows = (await session.execute(
        text(
            "SELECT COUNT(*) FROM agent_decisions "
            "WHERE entity_id='store-001' AND event_type='resupply_delivered'"
        )
    )).all()
    assert int(rows[0][0]) >= 1, (
        "Store agent must receive resupply_delivered event and register a decision"
    )


async def test_truck_arrived_event_created_on_arrival(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _drive_store_delivery(client, session)
    await _advance_until_delivered(client, 6)

    await session.rollback()
    rows = (await session.execute(
        text(
            "SELECT entity_id, entity_type FROM events "
            "WHERE event_type='truck_arrived'"
        )
    )).all()
    assert len(rows) >= 1, "truck_arrived event must be created when truck arrives"
    assert all(r.entity_type == "truck" for r in rows)


async def test_truck_arrived_triggers_truck_agent(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _drive_store_delivery(client, session)

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 6)

    await session.rollback()
    decision_count = (await session.execute(
        text(
            "SELECT COUNT(*) FROM agent_decisions "
            "WHERE agent_type='truck' AND event_type='truck_arrived'"
        )
    )).scalar()
    assert decision_count >= 1, (
        "Truck agent must receive truck_arrived event and register a decision"
    )

    arrived_events = (await session.execute(
        text("SELECT entity_id FROM events WHERE event_type='truck_arrived'")
    )).all()
    assert len(arrived_events) >= 1, "truck_arrived event must exist"
    truck_id = arrived_events[0].entity_id

    truck_row = (await session.execute(
        text("SELECT status, cargo, active_route_id FROM trucks WHERE id=:tid"),
        {"tid": truck_id},
    )).one()
    assert truck_row.status == "idle", (
        f"Truck must return to idle after arrival, got {truck_row.status}"
    )
    assert truck_row.cargo is None, "Cargo must be cleared after delivery"
    assert truck_row.active_route_id is None, "Active route must be cleared after arrival"


async def test_engine_blocked_event_published_to_redis(seeded_simulation_client, mock_valhalla):
    client, session, mock_redis = seeded_simulation_client

    from uuid import uuid4
    route_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO routes (id, truck_id, origin_type, origin_id, dest_type, dest_id, "
            "path, timestamps, eta_ticks, status, started_at) "
            "VALUES (:rid, 'truck-006', 'warehouse', 'warehouse-002', 'store', 'store-001', "
            "CAST(:path AS jsonb), CAST(:ts AS jsonb), 5, 'active', NOW())"
        ),
        {"rid": route_id, "path": "[[-46.6,-23.5],[-46.5,-23.5]]", "ts": "[0,10]"},
    )
    await session.execute(
        text(
            "UPDATE trucks SET status='in_transit', degradation=0.96, breakdown_risk=0.5, "
            "cargo=CAST(:cargo AS jsonb), active_route_id=:rid WHERE id='truck-006'"
        ),
        {
            "rid": route_id,
            "cargo": '{"material_id":"cimento","quantity_tons":10,"origin_type":"warehouse","origin_id":"warehouse-002","destination_type":"store","destination_id":"store-001"}',
        },
    )
    await session.commit()

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 1)

    matching_calls = []
    for call in mock_redis.publish.call_args_list:
        args = call.args
        if len(args) < 2:
            continue
        channel, payload = args[0], args[1]
        if channel != "nexus:events":
            continue
        payload_str = payload if isinstance(payload, str) else payload.decode("utf-8")
        if "engine_blocked_degraded_truck" in payload_str:
            matching_calls.append(payload_str)

    assert len(matching_calls) >= 1, (
        f"Expected engine_blocked_degraded_truck event published to nexus:events. "
        f"Got calls: {mock_redis.publish.call_args_list}"
    )


async def test_send_stock_with_owned_truck_emits_new_order(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_empty_warehouse(session)

    llm_t1 = make_entity_routing_llm(**{"warehouse-002": [WAREHOUSE_REQUEST_CIMENTO]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
        await advance_ticks_with_settle(client, 1)

    llm_t2 = make_entity_routing_llm(**{"factory-003": [FACTORY_SEND_CIMENTO]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t2):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    rows = (await session.execute(
        text(
            "SELECT event_type, entity_id, payload FROM events "
            "WHERE entity_id='truck-002' AND event_type IN ('new_order','contract_proposal') "
            "ORDER BY created_at DESC"
        )
    )).all()
    assert len(rows) >= 1, (
        "send_stock from factory-003 must emit a truck event for the owned truck-002"
    )
    assert rows[0].event_type == "new_order", (
        f"Owned idle truck (truck-002 proprietário of factory-003) must receive 'new_order'; "
        f"got {rows[0].event_type}"
    )


async def test_send_stock_fallback_to_contract_proposal(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_empty_warehouse(session)

    await session.execute(
        text("UPDATE trucks SET status='in_transit' WHERE id='truck-002'")
    )
    await session.commit()

    llm_t1 = make_entity_routing_llm(**{"warehouse-002": [WAREHOUSE_REQUEST_CIMENTO]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
        await advance_ticks_with_settle(client, 1)

    llm_t2 = make_entity_routing_llm(**{"factory-003": [FACTORY_SEND_CIMENTO]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t2):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    rows = (await session.execute(
        text(
            "SELECT event_type, entity_id FROM events "
            "WHERE event_type IN ('new_order','contract_proposal') "
            "AND payload->>'origin_id' = 'factory-003' "
            "ORDER BY created_at DESC"
        )
    )).all()
    assert len(rows) >= 1, (
        "When owned truck is busy, send_stock must still emit a truck event (contract_proposal)"
    )
    assert rows[0].event_type == "contract_proposal", (
        f"With owned truck busy, factory-003 send_stock must fallback to contract_proposal; "
        f"got {rows[0].event_type}"
    )
    terceiro_ids = (await session.execute(
        text("SELECT id FROM trucks WHERE truck_type='terceiro'")
    )).scalars().all()
    assert rows[0].entity_id in set(terceiro_ids), (
        f"Fallback event must target a terceiro truck; got {rows[0].entity_id}"
    )
