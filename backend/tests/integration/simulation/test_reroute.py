import json
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    make_entity_routing_llm,
)

pytestmark = pytest.mark.asyncio


_INITIAL_CARGO = {
    "material_id": "cimento",
    "quantity_tons": 10.0,
    "origin_type": "warehouse",
    "origin_id": "warehouse-002",
    "destination_type": "store",
    "destination_id": "store-001",
}

_INITIAL_PATH = [[-46.6, -23.5], [-46.5, -23.5]]
_INITIAL_TIMESTAMPS = [0, 10]


async def _park_all_trucks_far_away(session):
    await session.execute(
        text("UPDATE trucks SET status='maintenance' WHERE id <> 'truck-004'")
    )


async def _setup_truck_in_transit(session):
    await _park_all_trucks_far_away(session)

    route_id = uuid4()
    order_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO pending_orders "
            "(id, requester_type, requester_id, target_type, target_id, material_id, quantity_tons, status, age_ticks) "
            "VALUES (:oid, 'store', 'store-001', 'warehouse', 'warehouse-002', 'cimento', 10.0, 'confirmed', 0)"
        ),
        {"oid": order_id},
    )
    await session.execute(
        text(
            "INSERT INTO routes (id, truck_id, origin_type, origin_id, dest_type, dest_id, "
            "path, timestamps, eta_ticks, status, order_id, started_at) "
            "VALUES (:rid, 'truck-004', 'warehouse', 'warehouse-002', 'store', 'store-001', "
            "CAST(:path AS jsonb), CAST(:ts AS jsonb), 5, 'active', :oid, NOW())"
        ),
        {
            "rid": route_id,
            "path": json.dumps(_INITIAL_PATH),
            "ts": json.dumps(_INITIAL_TIMESTAMPS),
            "oid": order_id,
        },
    )
    await session.execute(
        text(
            "UPDATE trucks SET status='in_transit', degradation=0.0, breakdown_risk=0.0, "
            "cargo=CAST(:cargo AS jsonb), active_route_id=:rid WHERE id='truck-004'"
        ),
        {"cargo": json.dumps(_INITIAL_CARGO), "rid": route_id},
    )
    await session.commit()
    return str(route_id), str(order_id)


async def _inject_route_blocked(session, truck_id: str, tick_start: int = 0):
    await session.execute(
        text(
            "INSERT INTO events (id, event_type, source, entity_type, entity_id, payload, status, tick_start) "
            "VALUES (gen_random_uuid(), 'route_blocked', 'test', 'truck', :tid, CAST(:payload AS jsonb), 'active', :tick)"
        ),
        {
            "tid": truck_id,
            "payload": json.dumps({"reason": "highway closed"}),
            "tick": tick_start,
        },
    )
    await session.commit()


async def _fetch_route_data(session, route_id: str):
    result = await session.execute(
        text(
            "SELECT path::text AS path, timestamps::text AS timestamps, eta_ticks "
            "FROM routes WHERE id = :rid"
        ),
        {"rid": route_id},
    )
    return result.first()


async def test_reroute_updates_route_in_db(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    route_id, order_id = await _setup_truck_in_transit(session)
    await _inject_route_blocked(session, "truck-004")

    reroute_response = {
        "action": "reroute",
        "payload": {"order_id": order_id, "reason": "highway closed"},
        "reasoning_summary": "Route blocked, recomputing",
    }
    llm = make_entity_routing_llm(**{"truck-004": [reroute_response]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    route = await _fetch_route_data(session, route_id)
    assert route is not None

    new_path = json.loads(route.path)
    new_timestamps = json.loads(route.timestamps)
    assert new_path != _INITIAL_PATH
    assert new_timestamps != _INITIAL_TIMESTAMPS


async def test_reroute_preserves_truck_status(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    _, order_id = await _setup_truck_in_transit(session)
    await _inject_route_blocked(session, "truck-004")

    reroute_response = {
        "action": "reroute",
        "payload": {"order_id": order_id, "reason": "highway closed"},
        "reasoning_summary": "Route blocked, recomputing",
    }
    llm = make_entity_routing_llm(**{"truck-004": [reroute_response]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    result = await session.execute(
        text("SELECT status FROM trucks WHERE id='truck-004'")
    )
    assert result.scalar_one() == "in_transit"


async def test_reroute_event_resolved(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    _, order_id = await _setup_truck_in_transit(session)
    await _inject_route_blocked(session, "truck-004")

    reroute_response = {
        "action": "reroute",
        "payload": {"order_id": order_id, "reason": "highway closed"},
        "reasoning_summary": "Route blocked, recomputing",
    }
    llm = make_entity_routing_llm(**{"truck-004": [reroute_response]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    result = await session.execute(
        text(
            "SELECT status FROM events WHERE event_type='route_blocked' "
            "AND entity_id='truck-004' ORDER BY created_at DESC LIMIT 1"
        )
    )
    assert result.scalar_one() == "resolved"
