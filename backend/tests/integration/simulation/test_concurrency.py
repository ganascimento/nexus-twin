from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    make_combined_routing_llm,
    make_entity_routing_llm,
)

pytestmark = pytest.mark.asyncio


async def _setup_two_stores_low(session):
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
    await session.execute(
        text(
            "UPDATE warehouse_stocks SET stock=40, stock_reserved=0 "
            "WHERE warehouse_id='warehouse-002' AND material_id='cimento'"
        )
    )
    await session.execute(
        text("UPDATE store_stocks SET stock=1000 WHERE store_id IN ('store-001','store-002') AND material_id != 'cimento'")
    )
    await session.commit()


async def _stock_and_reserved(session):
    result = await session.execute(
        text(
            "SELECT stock, stock_reserved FROM warehouse_stocks "
            "WHERE warehouse_id='warehouse-002' AND material_id='cimento'"
        )
    )
    row = result.one()
    return float(row[0]), float(row[1])


async def test_concurrent_orders_atomic_reserve(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _setup_two_stores_low(session)

    store_order = {
        "action": "order_replenishment",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 30.0,
            "from_warehouse_id": "warehouse-002",
        },
        "reasoning_summary": "Low",
    }

    llm_t1 = make_entity_routing_llm(
        **{"store-001": [store_order], "store-002": [store_order]}
    )
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
        await advance_ticks_with_settle(client, 1)

    stock_after_orders, reserved_after_orders = await _stock_and_reserved(session)
    assert reserved_after_orders <= stock_after_orders, (
        f"Invariant broken after orders: reserved={reserved_after_orders} > stock={stock_after_orders}"
    )

    order_rows = (await session.execute(
        text(
            "SELECT id, requester_id FROM pending_orders "
            "WHERE target_id='warehouse-002' AND material_id='cimento' "
            "AND requester_id IN ('store-001','store-002') "
            "ORDER BY requester_id"
        )
    )).all()
    assert len(order_rows) == 2, f"Expected 2 pending orders, got {len(order_rows)}"
    store_001_order_id = str([r.id for r in order_rows if r.requester_id == "store-001"][0])
    store_002_order_id = str([r.id for r in order_rows if r.requester_id == "store-002"][0])

    warehouse_confirm_001 = {
        "action": "confirm_order",
        "payload": {"order_id": store_001_order_id, "quantity_tons": 30.0, "eta_ticks": 3},
        "reasoning_summary": "Confirm 001",
    }
    warehouse_confirm_002 = {
        "action": "confirm_order",
        "payload": {"order_id": store_002_order_id, "quantity_tons": 30.0, "eta_ticks": 3},
        "reasoning_summary": "Confirm 002",
    }

    llm_t2 = make_combined_routing_llm(
        by_entity={"warehouse-002": [warehouse_confirm_001, warehouse_confirm_002]}
    )
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t2):
        await advance_ticks_with_settle(client, 1)

    stock_final, reserved_final = await _stock_and_reserved(session)
    assert reserved_final <= stock_final, (
        f"CRITICAL invariant broken: stock_reserved={reserved_final} exceeds stock={stock_final}"
    )

    status_counts = {
        row[0]: row[1]
        for row in (await session.execute(
            text(
                "SELECT status, COUNT(*) FROM pending_orders "
                "WHERE target_id='warehouse-002' AND material_id='cimento' "
                "AND requester_id IN ('store-001','store-002') GROUP BY status"
            )
        )).all()
    }
    confirmed = status_counts.get("confirmed", 0)
    pending_or_rejected = status_counts.get("pending", 0) + status_counts.get("rejected", 0)

    assert confirmed == 1, (
        f"Expected exactly 1 confirmed order (only 40 ton of stock for 2x30 requests), got {confirmed}"
    )
    assert pending_or_rejected == 1, (
        f"The losing order must stay pending or become rejected; got {pending_or_rejected}"
    )
    assert reserved_final == 30.0, (
        f"Only one order (30 ton) should be reserved; got {reserved_final}"
    )
