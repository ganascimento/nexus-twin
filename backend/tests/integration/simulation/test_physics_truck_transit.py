import json
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import advance_n_ticks

pytestmark = pytest.mark.asyncio

_ROUTE_PATH = [[-46.6, -23.5], [-46.7, -23.4], [-46.8, -23.3]]
_ROUTE_TIMESTAMPS = [0, 2, 4]

_CARGO = {
    "material_id": "cimento",
    "quantity_tons": 10.0,
    "origin_type": "warehouse",
    "origin_id": "warehouse-002",
    "destination_type": "store",
    "destination_id": "store-001",
}


async def _setup_transit_truck(session, truck_id: str = "truck-004", eta_ticks: int = 3):
    route_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO routes (id, truck_id, origin_type, origin_id, dest_type, dest_id, "
            "path, timestamps, eta_ticks, status, started_at) "
            "VALUES (:rid, :tid, 'warehouse', 'warehouse-002', 'store', 'store-001', "
            "CAST(:path AS jsonb), CAST(:ts AS jsonb), :eta, 'active', NOW())"
        ),
        {
            "rid": route_id,
            "tid": truck_id,
            "path": json.dumps(_ROUTE_PATH),
            "ts": json.dumps(_ROUTE_TIMESTAMPS),
            "eta": eta_ticks,
        },
    )
    await session.execute(
        text(
            "UPDATE trucks SET status='in_transit', degradation=0.0, breakdown_risk=0.0, "
            "cargo=CAST(:cargo AS jsonb), active_route_id=:rid, "
            "current_lat=-23.5, current_lng=-46.6 WHERE id=:tid"
        ),
        {"cargo": json.dumps(_CARGO), "rid": route_id, "tid": truck_id},
    )
    await session.commit()
    return str(route_id)


# ---------------------------------------------------------------------------
# Truck position interpolation
# ---------------------------------------------------------------------------


async def test_truck_position_advances_along_route(seeded_simulation_client):
    client, session, _ = seeded_simulation_client
    await _setup_transit_truck(session, eta_ticks=3)

    initial = (await session.execute(
        text("SELECT current_lat, current_lng FROM trucks WHERE id='truck-004'")
    )).one()
    initial_lat, initial_lng = float(initial.current_lat), float(initial.current_lng)

    await advance_n_ticks(client, 1)
    await session.rollback()

    after = (await session.execute(
        text("SELECT current_lat, current_lng FROM trucks WHERE id='truck-004'")
    )).one()
    new_lat, new_lng = float(after.current_lat), float(after.current_lng)

    assert (new_lat, new_lng) != (initial_lat, initial_lng), (
        "Truck position must change after 1 tick in transit"
    )


async def test_truck_position_reaches_destination_on_arrival(seeded_simulation_client):
    client, session, _ = seeded_simulation_client
    route_id = await _setup_transit_truck(session, eta_ticks=1)

    await advance_n_ticks(client, 1)
    await session.rollback()

    final_pos = (await session.execute(
        text("SELECT current_lat, current_lng FROM trucks WHERE id='truck-004'")
    )).one()
    dest_lng, dest_lat = _ROUTE_PATH[-1]

    assert float(final_pos.current_lat) == pytest.approx(dest_lat, abs=0.01), (
        "Truck latitude must match route destination on arrival"
    )
    assert float(final_pos.current_lng) == pytest.approx(dest_lng, abs=0.01), (
        "Truck longitude must match route destination on arrival"
    )


# ---------------------------------------------------------------------------
# ETA countdown and delivery trigger
# ---------------------------------------------------------------------------


async def test_eta_decrements_each_tick(seeded_simulation_client):
    client, session, _ = seeded_simulation_client
    route_id = await _setup_transit_truck(session, eta_ticks=3)

    for expected_eta in [2, 1, 0]:
        await advance_n_ticks(client, 1)
        await session.rollback()
        eta = (await session.execute(
            text("SELECT eta_ticks FROM routes WHERE id=:rid"),
            {"rid": route_id},
        )).scalar_one()
        assert eta == expected_eta, f"ETA must be {expected_eta} after tick, got {eta}"


async def test_delivery_triggered_at_eta_zero(seeded_simulation_client):
    client, session, _ = seeded_simulation_client
    route_id = await _setup_transit_truck(session, eta_ticks=2)

    await advance_n_ticks(client, 1)
    await session.rollback()

    truck = (await session.execute(
        text("SELECT status, cargo FROM trucks WHERE id='truck-004'")
    )).one()
    assert truck.status == "in_transit", "Truck must still be in_transit after 1 tick (eta=1)"
    assert truck.cargo is not None, "Cargo must still be present before arrival"

    await advance_n_ticks(client, 1)
    await session.rollback()

    truck = (await session.execute(
        text("SELECT status, cargo, active_route_id FROM trucks WHERE id='truck-004'")
    )).one()
    assert truck.status == "idle", "Truck must be idle after eta reaches 0"
    assert truck.cargo is None, "Cargo must be cleared on delivery"
    assert truck.active_route_id is None, "Route must be cleared on delivery"

    route_status = (await session.execute(
        text("SELECT status FROM routes WHERE id=:rid"),
        {"rid": route_id},
    )).scalar_one()
    assert route_status == "completed", "Route status must be 'completed' on arrival"
