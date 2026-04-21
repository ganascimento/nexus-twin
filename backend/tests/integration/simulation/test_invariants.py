from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    get_stock,
    get_stock_reserved,
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


STORE_001_DEMAND_RATE_CIMENTO = 7.5


async def _stabilize_other_materials_at_store(session, store_id: str, skip_material: str):
    await session.execute(
        text(
            f"UPDATE store_stocks SET stock=1000 "
            f"WHERE store_id=:sid AND material_id != :skip"
        ),
        {"sid": store_id, "skip": skip_material},
    )


async def _setup_store_low_cimento(session):
    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
    await _stabilize_other_materials_at_store(session, "store-001", "cimento")
    await session.commit()


async def _setup_empty_warehouse(session):
    await session.execute(
        text("UPDATE warehouse_stocks SET stock=0, stock_reserved=0 WHERE warehouse_id='warehouse-002' AND material_id='cimento'")
    )
    await _stabilize_other_materials_at_store(session, "store-001", "cimento")
    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
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


async def _sum_warehouse_stock(session, warehouse_id: str, material_id: str) -> float:
    result = await session.execute(
        text(
            "SELECT stock FROM warehouse_stocks WHERE warehouse_id=:wid AND material_id=:mid"
        ),
        {"wid": warehouse_id, "mid": material_id},
    )
    value = result.scalar_one_or_none()
    return float(value) if value is not None else 0.0


async def _sum_factory_stock(session, factory_id: str, material_id: str) -> float:
    result = await session.execute(
        text(
            "SELECT stock FROM factory_products WHERE factory_id=:fid AND material_id=:mid"
        ),
        {"fid": factory_id, "mid": material_id},
    )
    value = result.scalar_one_or_none()
    return float(value) if value is not None else 0.0


async def _sum_store_stock(session, store_id: str, material_id: str) -> float:
    result = await session.execute(
        text(
            "SELECT stock FROM store_stocks WHERE store_id=:sid AND material_id=:mid"
        ),
        {"sid": store_id, "mid": material_id},
    )
    value = result.scalar_one_or_none()
    return float(value) if value is not None else 0.0


async def _truck_cargo_qty(session, material_id: str) -> float:
    result = await session.execute(
        text(
            "SELECT COALESCE(SUM((cargo->>'quantity_tons')::float), 0) FROM trucks "
            "WHERE cargo IS NOT NULL AND cargo->>'material_id' = :mid"
        ),
        {"mid": material_id},
    )
    return float(result.scalar_one())


async def _min_stock_any_table(session) -> tuple[float, float]:
    min_store = (await session.execute(text("SELECT COALESCE(MIN(stock), 0) FROM store_stocks"))).scalar_one()
    min_wh = (await session.execute(text("SELECT COALESCE(MIN(stock), 0) FROM warehouse_stocks"))).scalar_one()
    min_factory = (await session.execute(text("SELECT COALESCE(MIN(stock), 0) FROM factory_products"))).scalar_one()
    min_reserved_wh = (await session.execute(text("SELECT COALESCE(MIN(stock_reserved), 0) FROM warehouse_stocks"))).scalar_one()
    min_reserved_factory = (await session.execute(text("SELECT COALESCE(MIN(stock_reserved), 0) FROM factory_products"))).scalar_one()
    global_min_stock = min(float(min_store), float(min_wh), float(min_factory))
    global_min_reserved = min(float(min_reserved_wh), float(min_reserved_factory))
    return global_min_stock, global_min_reserved


async def _drive_cycle_to_in_transit_store(client, session):
    await _setup_store_low_cimento(session)
    initial_store = await _sum_store_stock(session, "store-001", "cimento")
    initial_warehouse = await _sum_warehouse_stock(session, "warehouse-002", "cimento")

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

    return order_id, initial_store, initial_warehouse


async def test_stock_conservation_store_to_warehouse_transit(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    order_id, initial_store, initial_warehouse = await _drive_cycle_to_in_transit_store(client, session)

    llm_hold = make_combined_routing_llm()

    await session.rollback()
    ticks_elapsed_before_cycle = 3
    baseline = float(initial_warehouse) + float(initial_store)
    max_demand_rate = STORE_001_DEMAND_RATE_CIMENTO

    for tick_index in range(6):
        with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
            await advance_ticks_with_settle(client, 1)
        await session.rollback()

        warehouse_stock = await _sum_warehouse_stock(session, "warehouse-002", "cimento")
        warehouse_reserved = float(await get_stock_reserved(session, "warehouse-002", "cimento") or 0.0)
        cargo_qty = await _truck_cargo_qty(session, "cimento")
        store_stock = await _sum_store_stock(session, "store-001", "cimento")

        ticks_elapsed_before_cycle += 1
        available_at_origin = warehouse_stock - warehouse_reserved
        system_total = available_at_origin + cargo_qty + store_stock
        consumed_by_demand = baseline - system_total
        max_demand_possible = max_demand_rate * ticks_elapsed_before_cycle

        assert consumed_by_demand >= -0.001, (
            f"tick {tick_index}: demand consumed cannot be negative: {consumed_by_demand}"
        )
        assert warehouse_reserved >= 0.0
        assert consumed_by_demand <= max_demand_possible + 0.001, (
            f"tick {tick_index}: consumption {consumed_by_demand} exceeds max possible demand {max_demand_possible}"
        )


async def test_stock_conservation_factory_to_warehouse_transit(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_empty_warehouse(session)

    initial_factory = await _sum_factory_stock(session, "factory-003", "cimento")
    initial_warehouse = await _sum_warehouse_stock(session, "warehouse-002", "cimento")

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

    baseline = float(initial_factory) + float(initial_warehouse)
    await session.rollback()

    llm_hold = make_combined_routing_llm()
    factory_production_rate = 0.0

    for tick_index in range(6):
        with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
            await advance_ticks_with_settle(client, 1)
        await session.rollback()

        factory_stock = await _sum_factory_stock(session, "factory-003", "cimento")
        factory_reserved = float(
            (await session.execute(
                text(
                    "SELECT COALESCE(stock_reserved, 0) FROM factory_products "
                    "WHERE factory_id='factory-003' AND material_id='cimento'"
                )
            )).scalar_one() or 0.0
        )
        warehouse_stock = await _sum_warehouse_stock(session, "warehouse-002", "cimento")
        cargo_qty = await _truck_cargo_qty(session, "cimento")

        available_at_origin = factory_stock - factory_reserved
        system_total = available_at_origin + cargo_qty + warehouse_stock
        production_added = system_total - baseline
        assert production_added >= -0.001, (
            f"tick {tick_index}: available+cargo+warehouse cannot decrease without external source: {production_added}"
        )
        assert production_added <= factory_production_rate * (tick_index + 1) + 0.001, (
            f"tick {tick_index}: production added {production_added} exceeds cumulative production"
        )


async def test_stock_reserved_never_exceeds_stock_per_tick(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client

    await session.execute(
        text(
            "UPDATE warehouse_stocks SET stock=40, stock_reserved=0 "
            "WHERE warehouse_id='warehouse-002' AND material_id='cimento'"
        )
    )
    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
    await session.execute(
        text(
            "INSERT INTO store_stocks (store_id, material_id, stock, demand_rate, reorder_point) "
            "VALUES ('store-002','cimento',1.0,5,10) "
            "ON CONFLICT (store_id, material_id) DO UPDATE SET stock=1.0"
        )
    )
    await _stabilize_other_materials_at_store(session, "store-001", "cimento")
    await _stabilize_other_materials_at_store(session, "store-002", "cimento")
    await session.commit()

    llm_t1 = make_entity_routing_llm(
        **{"store-001": [STORE_ORDER_CIMENTO], "store-002": [STORE_ORDER_CIMENTO]}
    )
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()

    order_rows = (await session.execute(
        text(
            "SELECT id, requester_id FROM pending_orders "
            "WHERE target_id='warehouse-002' AND material_id='cimento' "
            "AND requester_id IN ('store-001','store-002') ORDER BY requester_id"
        )
    )).all()
    assert len(order_rows) == 2
    o1 = str([r.id for r in order_rows if r.requester_id == "store-001"][0])
    o2 = str([r.id for r in order_rows if r.requester_id == "store-002"][0])

    confirm_1 = {
        "action": "confirm_order",
        "payload": {"order_id": o1, "quantity_tons": 30.0, "eta_ticks": 3},
        "reasoning_summary": "c1",
    }
    confirm_2 = {
        "action": "confirm_order",
        "payload": {"order_id": o2, "quantity_tons": 30.0, "eta_ticks": 3},
        "reasoning_summary": "c2",
    }
    llm_t2 = make_combined_routing_llm(by_entity={"warehouse-002": [confirm_1, confirm_2]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t2):
        await advance_ticks_with_settle(client, 1)

    llm_hold = make_combined_routing_llm()
    for _ in range(8):
        await session.rollback()
        row = (await session.execute(
            text(
                "SELECT stock, stock_reserved FROM warehouse_stocks "
                "WHERE warehouse_id='warehouse-002' AND material_id='cimento'"
            )
        )).one()
        assert float(row.stock_reserved) <= float(row.stock), (
            f"Invariant broken: stock_reserved={row.stock_reserved} exceeds stock={row.stock}"
        )
        with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
            await advance_ticks_with_settle(client, 1)


async def test_factory_stock_reserved_never_exceeds_stock_per_tick(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
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

    llm_hold = make_combined_routing_llm()
    for _ in range(8):
        await session.rollback()
        row = (await session.execute(
            text(
                "SELECT stock, stock_reserved FROM factory_products "
                "WHERE factory_id='factory-003' AND material_id='cimento'"
            )
        )).one()
        assert float(row.stock_reserved) <= float(row.stock), (
            f"factory invariant broken: stock_reserved={row.stock_reserved} exceeds stock={row.stock}"
        )
        with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
            await advance_ticks_with_settle(client, 1)


async def test_stock_never_negative(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
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

    llm_hold = make_combined_routing_llm()
    for _ in range(10):
        await session.rollback()
        min_stock, min_reserved = await _min_stock_any_table(session)
        assert min_stock >= 0.0, f"Found negative stock: {min_stock}"
        assert min_reserved >= 0.0, f"Found negative stock_reserved: {min_reserved}"
        with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
            await advance_ticks_with_settle(client, 1)


async def test_store_demand_caps_at_zero_stock(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client

    await session.execute(
        text(
            "UPDATE store_stocks SET stock=0.5, demand_rate=7.5 "
            "WHERE store_id='store-001' AND material_id='cimento'"
        )
    )
    await _stabilize_other_materials_at_store(session, "store-001", "cimento")
    await session.commit()

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    stock_after = await _sum_store_stock(session, "store-001", "cimento")
    assert stock_after == pytest.approx(0.0, abs=0.001), (
        f"Store stock must cap at 0 instead of going negative; got {stock_after}"
    )


async def test_truck_active_route_id_points_to_existing_route(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    order_id, _, _ = await _drive_cycle_to_in_transit_store(client, session)
    await session.rollback()

    orphan_rows = (await session.execute(
        text(
            "SELECT t.id, t.active_route_id FROM trucks t "
            "LEFT JOIN routes r ON r.id = t.active_route_id "
            "WHERE t.active_route_id IS NOT NULL AND (r.id IS NULL OR r.truck_id != t.id)"
        )
    )).all()
    assert len(orphan_rows) == 0, (
        f"trucks.active_route_id must point to a route owned by same truck; violations: {orphan_rows}"
    )


async def test_route_order_id_points_to_existing_order(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    order_id, _, _ = await _drive_cycle_to_in_transit_store(client, session)
    await session.rollback()

    orphan_rows = (await session.execute(
        text(
            "SELECT r.id FROM routes r "
            "LEFT JOIN pending_orders po ON po.id = r.order_id "
            "WHERE r.order_id IS NOT NULL AND po.id IS NULL"
        )
    )).all()
    assert len(orphan_rows) == 0, (
        f"routes.order_id must point to existing order; orphans: {orphan_rows}"
    )


async def test_no_duplicate_active_routes_per_truck(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _drive_cycle_to_in_transit_store(client, session)

    llm_hold = make_combined_routing_llm()
    for _ in range(6):
        await session.rollback()
        duplicates = (await session.execute(
            text(
                "SELECT truck_id, COUNT(*) FROM routes WHERE status='active' "
                "GROUP BY truck_id HAVING COUNT(*) > 1"
            )
        )).all()
        assert len(duplicates) == 0, (
            f"Duplicate active routes per truck: {duplicates}"
        )
        with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
            await advance_ticks_with_settle(client, 1)


async def test_truck_cargo_matches_route_order(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    order_id, _, _ = await _drive_cycle_to_in_transit_store(client, session)
    await session.rollback()

    row = (await session.execute(
        text(
            "SELECT t.id, t.cargo, r.order_id FROM trucks t "
            "JOIN routes r ON r.id = t.active_route_id "
            "WHERE t.status='in_transit' AND t.active_route_id IS NOT NULL"
        )
    )).first()
    assert row is not None
    cargo = row.cargo
    assert cargo is not None
    assert str(cargo.get("order_id")) == str(row.order_id), (
        f"Truck cargo.order_id ({cargo.get('order_id')}) != route.order_id ({row.order_id})"
    )


async def test_truck_cargo_matches_route_by_leg(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _drive_cycle_to_in_transit_store(client, session)
    await session.rollback()

    row = (await session.execute(
        text(
            "SELECT t.id, t.cargo, r.origin_type, r.origin_id, r.dest_type, r.dest_id, r.leg FROM trucks t "
            "JOIN routes r ON r.id = t.active_route_id "
            "WHERE t.status='in_transit' AND t.active_route_id IS NOT NULL"
        )
    )).first()
    assert row is not None
    cargo = row.cargo
    assert cargo is not None

    if row.leg == "pickup":
        # pickup leg: route goes truck -> cargo pickup location (cargo.origin)
        assert row.origin_type == "truck"
        assert cargo.get("origin_type") == row.dest_type, (
            f"pickup dest must match cargo.origin_type: cargo={cargo.get('origin_type')} "
            f"vs route.dest={row.dest_type}"
        )
        assert cargo.get("origin_id") == row.dest_id
    else:
        # delivery leg (or legacy): route.origin = cargo pickup, route.dest = cargo destination
        assert cargo.get("origin_type") == row.origin_type, (
            f"cargo.origin_type={cargo.get('origin_type')} vs route.origin_type={row.origin_type}"
        )
        assert cargo.get("origin_id") == row.origin_id
        assert cargo.get("destination_type") == row.dest_type
        assert cargo.get("destination_id") == row.dest_id
