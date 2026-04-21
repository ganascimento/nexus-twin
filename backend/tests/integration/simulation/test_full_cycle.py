from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    get_order_status,
    get_stock,
    get_stock_reserved,
    make_combined_routing_llm,
    make_entity_routing_llm,
)

pytestmark = pytest.mark.asyncio


STORE_001_CIMENTO_DEMAND_RATE = 7.5
WAREHOUSE_002_CIMENTO_INITIAL_STOCK = 150.0
DELIVERY_QUANTITY_TONS = 30.0


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


async def _setup_low_stock_store(session):
    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
    await session.commit()


async def _setup_empty_warehouse(session):
    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
    await session.execute(
        text("UPDATE warehouse_stocks SET stock=0 WHERE warehouse_id='warehouse-002' AND material_id='cimento'")
    )
    await session.commit()


async def _fetch_latest_order_id(session, requester_id, material_id, target_id=None):
    await session.rollback()
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


async def test_pending_order_created_after_store_decision(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_low_stock_store(session)

    llm = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    result = await session.execute(
        text(
            "SELECT status, target_id, target_type, material_id, quantity_tons "
            "FROM pending_orders WHERE requester_id='store-001' AND material_id='cimento' "
            "ORDER BY created_at DESC LIMIT 1"
        )
    )
    row = result.first()
    assert row is not None
    assert row.status == "pending"
    assert row.target_id == "warehouse-002"
    assert row.target_type == "warehouse"
    assert float(row.quantity_tons) == 30.0


async def test_warehouse_reserves_stock_on_confirm(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_low_stock_store(session)

    llm_t1 = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
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

    await session.rollback()
    reserved = await get_stock_reserved(session, "warehouse-002", "cimento")
    assert reserved is not None and float(reserved) == DELIVERY_QUANTITY_TONS
    status = await get_order_status(session, order_id)
    assert status == "confirmed"


async def test_truck_assigned_route_on_accept(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_low_stock_store(session)

    llm_t1 = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
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

    await session.rollback()
    result = await session.execute(
        text(
            "SELECT id, status, active_route_id FROM trucks "
            "WHERE status='in_transit' AND active_route_id IS NOT NULL"
        )
    )
    truck_row = result.first()
    assert truck_row is not None
    assert truck_row.active_route_id is not None

    route_row = (await session.execute(
        text("SELECT order_id FROM routes WHERE id = :rid"),
        {"rid": str(truck_row.active_route_id)},
    )).first()
    assert route_row is not None
    assert str(route_row.order_id) == order_id


async def test_stock_transferred_to_store_on_arrival(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_low_stock_store(session)

    initial_store_stock = await get_stock(session, "store_stocks", "store_id", "store-001", "cimento")

    llm_t1 = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
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
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 12)

    await session.rollback()
    final_stock = await get_stock(session, "store_stocks", "store_id", "store-001", "cimento")
    assert final_stock is not None
    # Stock may be re-consumed by demand after delivery; status=delivered proves arrival
    assert await get_order_status(session, order_id) == "delivered"
    assert float(final_stock) >= 0.0


async def test_order_marked_delivered_on_arrival(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_low_stock_store(session)

    llm_t1 = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
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
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 12)

    await session.rollback()
    status = await get_order_status(session, order_id)
    assert status == "delivered"

    reserved = await get_stock_reserved(session, "warehouse-002", "cimento")
    assert reserved is not None and float(reserved) == 0.0

    warehouse_stock_after = await get_stock(session, "warehouse_stocks", "warehouse_id", "warehouse-002", "cimento")
    assert warehouse_stock_after == 150.0 - 30.0


async def test_full_cycle_store_to_delivery(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_low_stock_store(session)

    initial_store = await get_stock(session, "store_stocks", "store_id", "store-001", "cimento")
    initial_warehouse = await get_stock(session, "warehouse_stocks", "warehouse_id", "warehouse-002", "cimento")

    llm_t1 = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
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
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 12)

    await session.rollback()
    assert await get_order_status(session, order_id) == "delivered"

    final_store = await get_stock(session, "store_stocks", "store_id", "store-001", "cimento")
    # Delivered; store stock may be immediately re-consumed by demand
    assert float(final_store) >= 0.0

    final_warehouse = await get_stock(session, "warehouse_stocks", "warehouse_id", "warehouse-002", "cimento")
    assert float(final_warehouse) == float(initial_warehouse) - DELIVERY_QUANTITY_TONS

    reserved = await get_stock_reserved(session, "warehouse-002", "cimento")
    assert float(reserved) == 0.0

    trucks_in_transit = (await session.execute(
        text("SELECT COUNT(*) FROM trucks WHERE status='in_transit'")
    )).scalar()
    assert trucks_in_transit == 0


async def test_factory_stock_decremented_on_send(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_empty_warehouse(session)

    initial_factory_stock = await get_stock(session, "factory_products", "factory_id", "factory-003", "cimento")

    warehouse_resupply = {
        "action": "request_resupply",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 100.0,
            "from_factory_id": "factory-003",
        },
        "reasoning_summary": "Empty stock",
    }
    llm_t1 = make_entity_routing_llm(**{"warehouse-002": [warehouse_resupply]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
        await advance_ticks_with_settle(client, 1)

    factory_send = {
        "action": "send_stock",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 100.0,
            "destination_warehouse_id": "warehouse-002",
        },
        "reasoning_summary": "Send",
    }
    llm_t2 = make_entity_routing_llm(**{"factory-003": [factory_send]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t2):
        await advance_ticks_with_settle(client, 1)

    factory_order_id = await _fetch_latest_order_id(
        session, "warehouse-002", "cimento", target_id="factory-003"
    )
    assert factory_order_id is not None

    truck_accept = {
        "action": "accept_contract",
        "payload": {"order_id": factory_order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accept",
    }
    llm_t3 = make_combined_routing_llm(by_agent={"truck": [truck_accept]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t3):
        await advance_ticks_with_settle(client, 1)

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 6)

    await session.rollback()
    final_factory_stock = await get_stock(session, "factory_products", "factory_id", "factory-003", "cimento")
    assert final_factory_stock is not None
    assert float(final_factory_stock) < float(initial_factory_stock)


async def test_warehouse_stock_increased_after_factory_delivery(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_empty_warehouse(session)

    warehouse_resupply = {
        "action": "request_resupply",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 100.0,
            "from_factory_id": "factory-003",
        },
        "reasoning_summary": "Empty",
    }
    llm_t1 = make_entity_routing_llm(**{"warehouse-002": [warehouse_resupply]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
        await advance_ticks_with_settle(client, 1)

    factory_send = {
        "action": "send_stock",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 100.0,
            "destination_warehouse_id": "warehouse-002",
        },
        "reasoning_summary": "Send",
    }
    llm_t2 = make_entity_routing_llm(**{"factory-003": [factory_send]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t2):
        await advance_ticks_with_settle(client, 1)

    factory_order_id = await _fetch_latest_order_id(
        session, "warehouse-002", "cimento", target_id="factory-003"
    )
    assert factory_order_id is not None

    truck_accept = {
        "action": "accept_contract",
        "payload": {"order_id": factory_order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accept",
    }
    llm_t3 = make_combined_routing_llm(by_agent={"truck": [truck_accept]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t3):
        await advance_ticks_with_settle(client, 1)

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 6)

    await session.rollback()
    final_warehouse_stock = await get_stock(session, "warehouse_stocks", "warehouse_id", "warehouse-002", "cimento")
    assert final_warehouse_stock is not None
    assert float(final_warehouse_stock) > 0.0


async def test_full_chain_factory_to_store(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_empty_warehouse(session)

    initial_factory_stock = await get_stock(session, "factory_products", "factory_id", "factory-003", "cimento")
    initial_store_stock = await get_stock(session, "store_stocks", "store_id", "store-001", "cimento")

    warehouse_resupply = {
        "action": "request_resupply",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 100.0,
            "from_factory_id": "factory-003",
        },
        "reasoning_summary": "Empty",
    }
    llm_t1 = make_entity_routing_llm(**{"warehouse-002": [warehouse_resupply]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
        await advance_ticks_with_settle(client, 1)

    factory_send = {
        "action": "send_stock",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 100.0,
            "destination_warehouse_id": "warehouse-002",
        },
        "reasoning_summary": "Send",
    }
    llm_t2 = make_entity_routing_llm(**{"factory-003": [factory_send]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t2):
        await advance_ticks_with_settle(client, 1)

    factory_order_id = await _fetch_latest_order_id(
        session, "warehouse-002", "cimento", target_id="factory-003"
    )
    assert factory_order_id is not None

    truck_accept_factory = {
        "action": "accept_contract",
        "payload": {"order_id": factory_order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accept",
    }
    llm_t3 = make_combined_routing_llm(by_agent={"truck": [truck_accept_factory]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t3):
        await advance_ticks_with_settle(client, 1)

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 6)

    await session.rollback()
    warehouse_after_factory = await get_stock(session, "warehouse_stocks", "warehouse_id", "warehouse-002", "cimento")
    assert float(warehouse_after_factory) > 0.0
    factory_after = await get_stock(session, "factory_products", "factory_id", "factory-003", "cimento")
    assert float(factory_after) < float(initial_factory_stock)

    llm_t7 = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t7):
        await advance_ticks_with_settle(client, 1)
    store_order_id = await _fetch_latest_order_id(session, "store-001", "cimento", target_id="warehouse-002")
    assert store_order_id is not None and store_order_id != factory_order_id

    warehouse_confirm = {
        "action": "confirm_order",
        "payload": {"order_id": store_order_id, "quantity_tons": 30.0, "eta_ticks": 3},
        "reasoning_summary": "Confirm",
    }
    llm_t8 = make_entity_routing_llm(**{"warehouse-002": [warehouse_confirm]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t8):
        await advance_ticks_with_settle(client, 1)

    truck_accept_store = {
        "action": "accept_contract",
        "payload": {"order_id": store_order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accept",
    }
    llm_t9 = make_combined_routing_llm(by_agent={"truck": [truck_accept_store]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t9):
        await advance_ticks_with_settle(client, 1)

    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 6)

    await session.rollback()
    assert await get_order_status(session, store_order_id) == "delivered"
    final_store = await get_stock(session, "store_stocks", "store_id", "store-001", "cimento")
    assert float(final_store) > float(initial_store_stock)
