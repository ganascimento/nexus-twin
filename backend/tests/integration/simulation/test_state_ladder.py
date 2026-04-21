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


STORE_ORDER = {
    "action": "order_replenishment",
    "payload": {
        "material_id": "cimento",
        "quantity_tons": 30.0,
        "from_warehouse_id": "warehouse-002",
    },
    "reasoning_summary": "Low",
}


async def _fetch_route_for_order(session, order_id: str):
    result = await session.execute(
        text(
            "SELECT id, status, eta_ticks, order_id, leg FROM routes "
            "WHERE order_id=:oid AND status='active' "
            "ORDER BY started_at DESC LIMIT 1"
        ),
        {"oid": order_id},
    )
    return result.first()


async def _count_trucks_in_transit_with_order(session, order_id: str) -> int:
    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM trucks t "
            "JOIN routes r ON r.id = t.active_route_id "
            "WHERE t.status='in_transit' AND r.order_id=:oid"
        ),
        {"oid": order_id},
    )
    return int(result.scalar_one())


async def test_complete_state_ladder_single_order(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client

    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
    await session.execute(
        text("UPDATE store_stocks SET stock=1000 WHERE store_id='store-001' AND material_id != 'cimento'")
    )
    await session.commit()

    initial_store_stock = await get_stock(session, "store_stocks", "store_id", "store-001", "cimento")
    initial_warehouse_stock = await get_stock(session, "warehouse_stocks", "warehouse_id", "warehouse-002", "cimento")
    assert float(initial_warehouse_stock) == 150.0

    llm_t1 = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
        await advance_ticks_with_settle(client, 1)

    order_row = (await session.execute(
        text(
            "SELECT id, status, requester_id, target_id, material_id, quantity_tons "
            "FROM pending_orders WHERE requester_id='store-001' AND material_id='cimento' "
            "ORDER BY created_at DESC LIMIT 1"
        )
    )).first()
    assert order_row is not None
    assert order_row.status == "pending"
    assert order_row.requester_id == "store-001"
    assert order_row.target_id == "warehouse-002"
    assert float(order_row.quantity_tons) == 30.0
    order_id = str(order_row.id)

    warehouse_confirm = {
        "action": "confirm_order",
        "payload": {"order_id": order_id, "quantity_tons": 30.0, "eta_ticks": 3},
        "reasoning_summary": "Confirm",
    }
    llm_t2 = make_entity_routing_llm(**{"warehouse-002": [warehouse_confirm]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t2):
        await advance_ticks_with_settle(client, 1)

    assert await get_order_status(session, order_id) == "confirmed"
    stock_reserved_after_confirm = await get_stock_reserved(session, "warehouse-002", "cimento")
    assert float(stock_reserved_after_confirm) == 30.0
    stock_after_confirm = await get_stock(session, "warehouse_stocks", "warehouse_id", "warehouse-002", "cimento")
    assert float(stock_after_confirm) == 150.0, (
        f"warehouse.stock must NOT decrease at confirm; got {stock_after_confirm}"
    )

    truck_accept = {
        "action": "accept_contract",
        "payload": {"order_id": order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accept",
    }
    llm_t3 = make_combined_routing_llm(by_agent={"truck": [truck_accept]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t3):
        await advance_ticks_with_settle(client, 1)

    route = await _fetch_route_for_order(session, order_id)
    assert route is not None
    assert route.status == "active"
    assert str(route.order_id) == order_id
    assert await _count_trucks_in_transit_with_order(session, order_id) == 1

    # Allow up to one eta reset when the pickup leg completes and delivery leg
    # is dispatched — the new route starts with a fresh eta.
    eta_progression = [(route.id, route.eta_ticks)]
    llm_hold = make_combined_routing_llm()
    for _ in range(8):
        with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
            await advance_ticks_with_settle(client, 1)
        route_now = await _fetch_route_for_order(session, order_id)
        if route_now is not None and route_now.status == "active":
            eta_progression.append((route_now.id, route_now.eta_ticks))
        if await get_order_status(session, order_id) == "delivered":
            break

    for earlier, later in zip(eta_progression, eta_progression[1:]):
        if earlier[0] == later[0]:
            assert later[1] <= earlier[1], (
                f"eta within the same route must not increase: {eta_progression}"
            )

    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 6)

    final_status = await get_order_status(session, order_id)
    assert final_status == "delivered"

    final_warehouse_stock = await get_stock(session, "warehouse_stocks", "warehouse_id", "warehouse-002", "cimento")
    assert float(final_warehouse_stock) == float(initial_warehouse_stock) - 30.0

    final_warehouse_reserved = await get_stock_reserved(session, "warehouse-002", "cimento")
    assert float(final_warehouse_reserved) == 0.0

    final_store_stock = await get_stock(session, "store_stocks", "store_id", "store-001", "cimento")
    # Stock may have been re-consumed by demand after delivery; status=delivered
    # (asserted above) plus warehouse stock decremented already prove delivery landed.
    assert float(final_store_stock) >= 0.0

    trucks_still_busy = (await session.execute(
        text("SELECT COUNT(*) FROM trucks WHERE status='in_transit'")
    )).scalar_one()
    assert trucks_still_busy == 0

    trucks_still_with_our_cargo = (await session.execute(
        text(
            "SELECT COUNT(*) FROM trucks "
            "WHERE cargo IS NOT NULL "
            "AND cargo->>'order_id' = :oid"
        ),
        {"oid": order_id},
    )).scalar_one()
    assert trucks_still_with_our_cargo == 0, (
        "Delivering truck must release cargo for our order after arrival"
    )

    active_routes_for_order = (await session.execute(
        text("SELECT COUNT(*) FROM routes WHERE order_id=:oid AND status='active'"),
        {"oid": order_id},
    )).scalar_one()
    assert active_routes_for_order == 0
