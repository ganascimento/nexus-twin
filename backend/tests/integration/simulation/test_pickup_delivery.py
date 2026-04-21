from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    make_combined_routing_llm,
    make_entity_routing_llm,
)

pytestmark = pytest.mark.asyncio


STORE_ORDER = {
    "action": "order_replenishment",
    "payload": {
        "material_id": "cimento",
        "quantity_tons": 15.0,
        "from_warehouse_id": "warehouse-002",
    },
    "reasoning_summary": "Low stock",
}


async def _setup_store_low_cimento(session):
    await session.execute(
        text(
            "UPDATE store_stocks SET stock=1.0 "
            "WHERE store_id='store-001' AND material_id='cimento'"
        )
    )
    await session.execute(
        text(
            "UPDATE store_stocks SET stock=1000 "
            "WHERE store_id='store-001' AND material_id != 'cimento'"
        )
    )
    await session.commit()


async def _drive_to_accept(client, session):
    await _setup_store_low_cimento(session)

    with patch(
        "src.agents.base.ChatOpenAI",
        return_value=make_entity_routing_llm(**{"store-001": [STORE_ORDER]}),
    ):
        await advance_ticks_with_settle(client, 1)

    row = (await session.execute(
        text(
            "SELECT id FROM pending_orders WHERE requester_id='store-001' "
            "AND material_id='cimento' ORDER BY created_at DESC LIMIT 1"
        )
    )).first()
    order_id = str(row.id)

    warehouse_confirm = {
        "action": "confirm_order",
        "payload": {"order_id": order_id, "quantity_tons": 15.0, "eta_ticks": 3},
        "reasoning_summary": "Confirm",
    }
    with patch(
        "src.agents.base.ChatOpenAI",
        return_value=make_entity_routing_llm(**{"warehouse-002": [warehouse_confirm]}),
    ):
        await advance_ticks_with_settle(client, 1)

    truck_accept = {
        "action": "accept_contract",
        "payload": {"order_id": order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accept",
    }
    with patch(
        "src.agents.base.ChatOpenAI",
        return_value=make_combined_routing_llm(by_agent={"truck": [truck_accept]}),
    ):
        await advance_ticks_with_settle(client, 1)

    return order_id


async def test_accept_creates_pickup_leg_then_delivery_leg(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client
    order_id = await _drive_to_accept(client, session)

    await session.rollback()
    # Immediately after accept, there must be one active route with leg='pickup'
    pickup_rows = (await session.execute(
        text(
            "SELECT id, leg, origin_type, dest_type FROM routes "
            "WHERE order_id = :oid AND status='active'"
        ),
        {"oid": order_id},
    )).all()
    assert len(pickup_rows) == 1
    assert pickup_rows[0].leg == "pickup"
    assert pickup_rows[0].origin_type == "truck"
    assert pickup_rows[0].dest_type == "warehouse"

    # Advance enough ticks so pickup completes and delivery is dispatched
    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 12)

    await session.rollback()
    all_rows = (await session.execute(
        text(
            "SELECT leg, status, origin_type, dest_type FROM routes "
            "WHERE order_id = :oid ORDER BY started_at"
        ),
        {"oid": order_id},
    )).all()

    # Expect 2 rows: pickup (completed) + delivery (completed or active)
    assert len(all_rows) == 2
    legs = [r.leg for r in all_rows]
    assert legs == ["pickup", "delivery"]
    assert all_rows[0].status == "completed"
    # Delivery leg goes warehouse -> store
    assert all_rows[1].origin_type == "warehouse"
    assert all_rows[1].dest_type == "store"

    # Final order should be delivered
    final_status = (await session.execute(
        text("SELECT status FROM pending_orders WHERE id=:oid"),
        {"oid": order_id},
    )).scalar_one()
    assert final_status == "delivered"


async def test_truck_keeps_cargo_between_pickup_and_delivery(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client
    order_id = await _drive_to_accept(client, session)

    await session.rollback()
    # During pickup leg: truck has cargo; target material must match order
    row = (await session.execute(
        text(
            "SELECT t.cargo, r.leg FROM trucks t "
            "JOIN routes r ON r.id = t.active_route_id "
            "WHERE t.status='in_transit' AND r.order_id=:oid"
        ),
        {"oid": order_id},
    )).first()
    assert row is not None
    assert row.leg == "pickup"
    cargo = row.cargo
    assert cargo is not None
    assert cargo.get("material_id") == "cimento"
    assert cargo.get("quantity_tons") == 15.0
    assert cargo.get("destination_type") == "store"
    assert cargo.get("destination_id") == "store-001"

    # Advance pickup completion; delivery leg should be active with SAME cargo
    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 4)

    await session.rollback()
    row2 = (await session.execute(
        text(
            "SELECT t.cargo, r.leg FROM trucks t "
            "JOIN routes r ON r.id = t.active_route_id "
            "WHERE r.order_id=:oid AND r.status='active'"
        ),
        {"oid": order_id},
    )).first()
    if row2 is not None:
        # Still in transit: must be delivery leg with preserved cargo
        if row2.leg == "delivery":
            assert row2.cargo is not None
            assert row2.cargo.get("material_id") == "cimento"
            assert row2.cargo.get("quantity_tons") == 15.0


async def test_stock_not_consumed_on_pickup_arrival(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    initial_wh_stock = (await session.execute(
        text(
            "SELECT stock FROM warehouse_stocks "
            "WHERE warehouse_id='warehouse-002' AND material_id='cimento'"
        )
    )).scalar_one()

    order_id = await _drive_to_accept(client, session)

    # Advance just enough for pickup to complete (eta=1 to ~3 ticks for mock_valhalla)
    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 3)

    await session.rollback()
    rows = (await session.execute(
        text(
            "SELECT leg, status FROM routes WHERE order_id=:oid ORDER BY started_at"
        ),
        {"oid": order_id},
    )).all()
    # If pickup has just completed and delivery is mid-trip, warehouse stock
    # must NOT have been deducted yet (consume happens on delivery arrival).
    if len(rows) == 2 and rows[0].status == "completed" and rows[1].status == "active":
        wh_stock_now = (await session.execute(
            text(
                "SELECT stock FROM warehouse_stocks "
                "WHERE warehouse_id='warehouse-002' AND material_id='cimento'"
            )
        )).scalar_one()
        assert float(wh_stock_now) == float(initial_wh_stock), (
            "warehouse stock must not be consumed on pickup arrival; "
            "it is only consumed when delivery arrives at destination"
        )
