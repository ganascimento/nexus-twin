import json
from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    get_stock,
    get_stock_reserved,
    make_combined_routing_llm,
    make_entity_routing_llm,
    make_llm_responses,
)

pytestmark = pytest.mark.asyncio


STORE_ORDER = {
    "action": "order_replenishment",
    "payload": {
        "material_id": "cimento",
        "quantity_tons": 30.0,
        "from_warehouse_id": "warehouse-002",
    },
    "reasoning_summary": "Stock below reorder point",
}

HOLD = {"action": "hold", "payload": None, "reasoning_summary": "no-op"}


async def _insert_confirmed_order(
    session,
    *,
    requester_type: str,
    requester_id: str,
    target_type: str,
    target_id: str,
    material_id: str,
    quantity_tons: float,
) -> str:
    result = await session.execute(
        text(
            "INSERT INTO pending_orders "
            "(id, requester_type, requester_id, target_type, target_id, material_id, quantity_tons, status, age_ticks) "
            "VALUES (gen_random_uuid(), :rt, :rid, :tt, :tid, :mid, :qty, 'confirmed', 0) "
            "RETURNING id"
        ),
        {
            "rt": requester_type, "rid": requester_id,
            "tt": target_type, "tid": target_id,
            "mid": material_id, "qty": quantity_tons,
        },
    )
    return str(result.scalar_one())


async def _set_warehouse_reserved(session, warehouse_id: str, material_id: str, reserved: float):
    await session.execute(
        text(
            "UPDATE warehouse_stocks SET stock_reserved=:r "
            "WHERE warehouse_id=:wid AND material_id=:mid"
        ),
        {"r": reserved, "wid": warehouse_id, "mid": material_id},
    )


async def _set_factory_reserved(session, factory_id: str, material_id: str, reserved: float):
    await session.execute(
        text(
            "UPDATE factory_products SET stock_reserved=:r "
            "WHERE factory_id=:fid AND material_id=:mid"
        ),
        {"r": reserved, "fid": factory_id, "mid": material_id},
    )


async def _get_factory_reserved(session, factory_id: str, material_id: str) -> float | None:
    result = await session.execute(
        text(
            "SELECT stock_reserved FROM factory_products "
            "WHERE factory_id=:fid AND material_id=:mid"
        ),
        {"fid": factory_id, "mid": material_id},
    )
    return result.scalar_one_or_none()


async def _setup_in_transit_truck(
    session,
    truck_id: str,
    *,
    origin_type: str,
    origin_id: str,
    dest_type: str,
    dest_id: str,
    material_id: str = "cimento",
    quantity_tons: float = 10.0,
) -> str:
    cargo_json = json.dumps({
        "material_id": material_id,
        "quantity_tons": quantity_tons,
        "origin_type": origin_type,
        "origin_id": origin_id,
        "destination_type": dest_type,
        "destination_id": dest_id,
    })
    await session.execute(
        text(
            "UPDATE trucks SET status='in_transit', "
            "cargo=CAST(:cargo AS JSONB), "
            "current_lat=-23.5, current_lng=-46.6 "
            "WHERE id=:tid"
        ),
        {"tid": truck_id, "cargo": cargo_json},
    )
    result = await session.execute(
        text(
            "INSERT INTO routes ("
            "  id, truck_id, origin_type, origin_id, dest_type, dest_id, "
            "  path, timestamps, eta_ticks, status, started_at"
            ") VALUES ("
            "  gen_random_uuid(), :tid, :ot, :oid, :dt, :did, "
            "  CAST(:path AS JSONB), CAST(:ts AS JSONB), 2, 'active', NOW()"
            ") RETURNING id"
        ),
        {
            "tid": truck_id,
            "ot": origin_type, "oid": origin_id,
            "dt": dest_type, "did": dest_id,
            "path": json.dumps([[-46.6, -23.5], [-46.5, -23.5]]),
            "ts": json.dumps([0, 2]),
        },
    )
    route_id = result.scalar_one()
    await session.execute(
        text("UPDATE trucks SET active_route_id=:rid WHERE id=:tid"),
        {"rid": route_id, "tid": truck_id},
    )
    return str(route_id)


async def test_store_deletion_releases_warehouse_reserved_stock(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    await _insert_confirmed_order(
        session,
        requester_type="store", requester_id="store-001",
        target_type="warehouse", target_id="warehouse-002",
        material_id="cimento", quantity_tons=30.0,
    )
    await _set_warehouse_reserved(session, "warehouse-002", "cimento", 30.0)
    await session.commit()

    resp = await client.delete("/entities/stores/store-001")
    assert resp.status_code == 200

    await session.rollback()
    reserved = await get_stock_reserved(session, "warehouse-002", "cimento")
    assert reserved is not None
    assert float(reserved) == 0.0


async def test_factory_deletion_releases_factory_reserved_stock(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    await _insert_confirmed_order(
        session,
        requester_type="warehouse", requester_id="warehouse-002",
        target_type="factory", target_id="factory-003",
        material_id="cimento", quantity_tons=100.0,
    )
    await _set_factory_reserved(session, "factory-003", "cimento", 100.0)
    await session.commit()

    resp = await client.delete("/entities/factories/factory-003")
    assert resp.status_code == 200

    await session.rollback()
    reserved = await _get_factory_reserved(session, "factory-003", "cimento")
    # Factory may be deleted; if still queryable, reserved must be zero.
    # If deletion cascades products, we assume row is gone (None) — also acceptable.
    if reserved is not None:
        assert float(reserved) == 0.0


async def test_warehouse_deletion_releases_upstream_factory_reserved(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    await _insert_confirmed_order(
        session,
        requester_type="warehouse", requester_id="warehouse-002",
        target_type="factory", target_id="factory-003",
        material_id="cimento", quantity_tons=100.0,
    )
    await _set_factory_reserved(session, "factory-003", "cimento", 100.0)
    await session.commit()

    resp = await client.delete("/entities/warehouses/warehouse-002")
    assert resp.status_code == 200

    await session.rollback()
    reserved = await _get_factory_reserved(session, "factory-003", "cimento")
    assert reserved is not None
    assert float(reserved) == 0.0


async def test_truck_in_transit_to_deleted_store_handles_gracefully(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    await _setup_in_transit_truck(
        session,
        "truck-004",
        origin_type="warehouse", origin_id="warehouse-002",
        dest_type="store", dest_id="store-001",
    )
    await session.commit()

    resp = await client.delete("/entities/stores/store-001")
    assert resp.status_code == 200

    hold_llm = make_llm_responses(*([HOLD] * 20))
    with patch("src.agents.base.ChatOpenAI", return_value=hold_llm):
        await advance_ticks_with_settle(client, 4)

    await session.rollback()
    truck_row = (await session.execute(
        text(
            "SELECT status, cargo, active_route_id FROM trucks WHERE id='truck-004'"
        )
    )).first()
    assert truck_row is not None
    assert truck_row.status == "idle"
    assert truck_row.cargo is None
    assert truck_row.active_route_id is None

    route_statuses = (await session.execute(
        text(
            "SELECT status FROM routes "
            "WHERE truck_id='truck-004' ORDER BY started_at DESC"
        )
    )).all()
    assert len(route_statuses) >= 1
    latest = route_statuses[0].status
    assert latest in ("interrupted", "cancelled", "completed")
    # Delivered path should not be marked completed when destination was deleted.
    assert latest != "completed"


async def test_truck_in_transit_from_deleted_warehouse(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    await _setup_in_transit_truck(
        session,
        "truck-004",
        origin_type="warehouse", origin_id="warehouse-002",
        dest_type="store", dest_id="store-002",
    )
    await session.commit()

    resp = await client.delete("/entities/warehouses/warehouse-002")
    assert resp.status_code == 200

    hold_llm = make_llm_responses(*([HOLD] * 20))
    with patch("src.agents.base.ChatOpenAI", return_value=hold_llm):
        await advance_ticks_with_settle(client, 4)

    await session.rollback()
    truck_row = (await session.execute(
        text(
            "SELECT status, cargo, active_route_id FROM trucks WHERE id='truck-004'"
        )
    )).first()
    assert truck_row is not None
    assert truck_row.status == "idle"
    assert truck_row.cargo is None
    assert truck_row.active_route_id is None


async def test_order_cancelled_releases_reserved(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    order_id = await _insert_confirmed_order(
        session,
        requester_type="store", requester_id="store-001",
        target_type="warehouse", target_id="warehouse-002",
        material_id="cimento", quantity_tons=30.0,
    )
    await _set_warehouse_reserved(session, "warehouse-002", "cimento", 30.0)
    await session.commit()

    resp = await client.delete("/entities/stores/store-001")
    assert resp.status_code == 200

    await session.rollback()
    reserved = await get_stock_reserved(session, "warehouse-002", "cimento")
    assert reserved is not None
    assert float(reserved) == 0.0

    order_status = (await session.execute(
        text("SELECT status FROM pending_orders WHERE id=:oid"),
        {"oid": order_id},
    )).scalar_one()
    assert order_status == "cancelled"
