from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    make_combined_routing_llm,
)

pytestmark = pytest.mark.asyncio


async def _setup_in_transit_with_high_degradation(session, degradation: float = 0.96):
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
            "UPDATE trucks SET status='in_transit', degradation=:deg, breakdown_risk=0.5, "
            "cargo=CAST(:cargo AS jsonb), active_route_id=:rid WHERE id='truck-006'"
        ),
        {
            "deg": degradation,
            "rid": route_id,
            "cargo": '{"material_id":"cimento","quantity_tons":10,"origin_type":"warehouse","origin_id":"warehouse-002","destination_type":"store","destination_id":"store-001"}',
        },
    )
    await session.commit()
    return route_id


async def _truck_state(session, truck_id: str):
    result = await session.execute(
        text(
            "SELECT status, cargo::text AS cargo, active_route_id FROM trucks WHERE id=:tid"
        ),
        {"tid": truck_id},
    )
    return result.first()


async def test_degraded_trip_blocks_truck(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_in_transit_with_high_degradation(session)

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 1)

    state = await _truck_state(session, "truck-006")
    assert state.status != "in_transit", (
        f"Truck with degradation>=0.95 must leave in_transit, got {state.status}"
    )


async def test_degraded_trip_clears_cargo(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_in_transit_with_high_degradation(session)

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 1)

    state = await _truck_state(session, "truck-006")
    assert state.cargo in (None, "null"), (
        f"Blocked truck must have cargo cleared or transferred to rescue; "
        f"got cargo={state.cargo}"
    )


async def test_degraded_trip_releases_route(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_in_transit_with_high_degradation(session)

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 1)

    state = await _truck_state(session, "truck-006")
    assert state.active_route_id is None, (
        f"Blocked truck must release active_route_id; got {state.active_route_id}"
    )


async def test_degraded_trip_not_idle_state(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_in_transit_with_high_degradation(session)

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 1)

    state = await _truck_state(session, "truck-006")
    assert state.status in ("broken", "maintenance"), (
        f"Degraded truck must be broken or maintenance, not {state.status}"
    )
