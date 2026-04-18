from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    make_entity_routing_llm,
    make_routing_llm,
)

pytestmark = pytest.mark.asyncio


async def _set_low_store_stock(session, store_id: str, material_id: str, stock: float):
    await session.execute(
        text("UPDATE store_stocks SET stock=:stock WHERE store_id=:sid AND material_id=:mid"),
        {"stock": stock, "sid": store_id, "mid": material_id},
    )


async def _empty_warehouse_stock(session, warehouse_id: str, material_id: str):
    await session.execute(
        text("UPDATE warehouse_stocks SET stock=0 WHERE warehouse_id=:wid AND material_id=:mid"),
        {"wid": warehouse_id, "mid": material_id},
    )


async def _fetch_pending_order(session, store_id: str, material_id: str):
    result = await session.execute(
        text(
            "SELECT id, age_ticks FROM pending_orders "
            "WHERE requester_id=:sid AND material_id=:mid AND status='pending' "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"sid": store_id, "mid": material_id},
    )
    return result.one_or_none()


async def _fetch_rejected_order(session, store_id: str, material_id: str):
    result = await session.execute(
        text(
            "SELECT id, age_ticks, retry_after_tick, status FROM pending_orders "
            "WHERE requester_id=:sid AND material_id=:mid AND status='rejected' "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"sid": store_id, "mid": material_id},
    )
    return result.one_or_none()


async def _count_order_replenishment_decisions(session, store_id: str) -> int:
    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM agent_decisions "
            "WHERE entity_id=:sid AND action='order_replenishment'"
        ),
        {"sid": store_id},
    )
    return result.scalar_one()


STORE_ORDER = {
    "action": "order_replenishment",
    "payload": {
        "material_id": "cimento",
        "quantity_tons": 30.0,
        "from_warehouse_id": "warehouse-002",
    },
    "reasoning_summary": "Stock below reorder point",
}


async def test_rejected_order_respects_backoff(seeded_simulation_client, mock_valhalla):
    client, session, mock_redis = seeded_simulation_client

    await _empty_warehouse_stock(session, "warehouse-002", "cimento")
    await _set_low_store_stock(session, "store-001", "cimento", 1.0)
    await session.execute(
        text("UPDATE store_stocks SET stock=1000 WHERE store_id='store-001' AND material_id != 'cimento'")
    )
    await session.commit()

    tick1_llm = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
    with patch("src.agents.base.ChatOpenAI", return_value=tick1_llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    pending = await _fetch_pending_order(session, "store-001", "cimento")
    assert pending is not None, "Store agent did not create pending order in tick 1"
    order_id = pending[0]

    warehouse_reject = {
        "action": "reject_order",
        "payload": {
            "order_id": str(order_id),
            "reason": "insufficient_stock",
            "retry_after_ticks": 5,
        },
        "reasoning_summary": "No stock available",
    }
    tick2_llm = make_routing_llm(warehouse=[warehouse_reject])
    with patch("src.agents.base.ChatOpenAI", return_value=tick2_llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    rejected = await _fetch_rejected_order(session, "store-001", "cimento")
    assert rejected is not None, "Warehouse did not reject the order"
    rejected_id, age_at_rejection, retry_after_tick, _ = rejected
    assert rejected_id == order_id
    assert retry_after_tick is not None
    assert retry_after_tick == age_at_rejection + 5

    decisions_before_window = await _count_order_replenishment_decisions(session, "store-001")

    canary_llm = make_entity_routing_llm(
        **{"store-001": [STORE_ORDER, STORE_ORDER, STORE_ORDER]}
    )
    with patch("src.agents.base.ChatOpenAI", return_value=canary_llm):
        await advance_ticks_with_settle(client, 3)

    await session.rollback()
    age_mid = (await session.execute(
        text("SELECT age_ticks FROM pending_orders WHERE id=:id"), {"id": str(order_id)}
    )).scalar_one()
    assert age_mid < retry_after_tick

    decisions_mid_window = await _count_order_replenishment_decisions(session, "store-001")
    assert decisions_mid_window == decisions_before_window, (
        "Store agent must NOT be woken during backoff window"
    )
    assert len(canary_llm._entity_queues["store-001"]) == 3, (
        "Canary queue must be untouched during backoff — any consumption "
        "implies the store agent was triggered when it should have been suppressed"
    )

    retry_llm = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
    with patch("src.agents.base.ChatOpenAI", return_value=retry_llm):
        await advance_ticks_with_settle(client, 2)

    await session.rollback()
    age_after = (await session.execute(
        text("SELECT age_ticks FROM pending_orders WHERE id=:id"), {"id": str(order_id)}
    )).scalar_one()
    assert age_after >= retry_after_tick

    decisions_after_window = await _count_order_replenishment_decisions(session, "store-001")
    assert decisions_after_window > decisions_before_window


async def test_retry_creates_new_order(seeded_simulation_client, mock_valhalla):
    client, session, mock_redis = seeded_simulation_client

    await _empty_warehouse_stock(session, "warehouse-002", "cimento")
    await _set_low_store_stock(session, "store-001", "cimento", 1.0)
    await session.commit()

    tick1_llm = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
    with patch("src.agents.base.ChatOpenAI", return_value=tick1_llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    pending = await _fetch_pending_order(session, "store-001", "cimento")
    assert pending is not None
    original_order_id = pending[0]

    warehouse_reject = {
        "action": "reject_order",
        "payload": {
            "order_id": str(original_order_id),
            "reason": "insufficient_stock",
            "retry_after_ticks": 5,
        },
        "reasoning_summary": "No stock",
    }
    tick2_llm = make_routing_llm(warehouse=[warehouse_reject])
    with patch("src.agents.base.ChatOpenAI", return_value=tick2_llm):
        await advance_ticks_with_settle(client, 1)

    hold_llm = make_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=hold_llm):
        await advance_ticks_with_settle(client, 3)

    retry_llm = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
    with patch("src.agents.base.ChatOpenAI", return_value=retry_llm):
        await advance_ticks_with_settle(client, 2)

    await session.rollback()
    original_status = (await session.execute(
        text("SELECT status FROM pending_orders WHERE id=:id"), {"id": str(original_order_id)}
    )).scalar_one()
    assert original_status == "rejected"

    result = await session.execute(
        text(
            "SELECT id, status FROM pending_orders "
            "WHERE requester_id='store-001' AND material_id='cimento' AND id != :oid "
            "ORDER BY created_at DESC"
        ),
        {"oid": str(original_order_id)},
    )
    new_orders = result.all()
    assert len(new_orders) >= 1, "No new order created after retry"
    assert any(o.status in ("pending", "confirmed") for o in new_orders)
