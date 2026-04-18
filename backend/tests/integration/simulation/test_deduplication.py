from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
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

WAREHOUSE_REQUEST_RESUPPLY = {
    "action": "request_resupply",
    "payload": {
        "material_id": "cimento",
        "quantity_tons": 100.0,
        "from_factory_id": "factory-003",
    },
    "reasoning_summary": "Empty",
}

FACTORY_SEND_STOCK = {
    "action": "send_stock",
    "payload": {
        "material_id": "cimento",
        "quantity_tons": 100.0,
        "destination_warehouse_id": "warehouse-002",
    },
    "reasoning_summary": "Send",
}


async def _count_active_orders(session, requester_id, material_id, target_id=None):
    where = "requester_id=:rid AND material_id=:mid AND status IN ('pending','confirmed')"
    params = {"rid": requester_id, "mid": material_id}
    if target_id is not None:
        where += " AND target_id=:tid"
        params["tid"] = target_id
    result = await session.execute(
        text(f"SELECT COUNT(*) FROM pending_orders WHERE {where}"), params
    )
    return int(result.scalar_one())


async def test_store_does_not_duplicate_orders(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client

    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
    await session.commit()

    llm = make_entity_routing_llm(
        **{"store-001": [STORE_ORDER, STORE_ORDER, STORE_ORDER]}
    )
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 3)

    count = await _count_active_orders(session, "store-001", "cimento", "warehouse-002")
    assert count == 1, f"Store dedup failed: {count} active orders"


async def test_warehouse_does_not_duplicate_resupply(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client

    await session.execute(
        text(
            "UPDATE warehouse_stocks SET stock=5, min_stock=100 "
            "WHERE warehouse_id='warehouse-002' AND material_id='cimento'"
        )
    )
    await session.commit()

    llm = make_entity_routing_llm(
        **{
            "warehouse-002": [
                WAREHOUSE_REQUEST_RESUPPLY,
                WAREHOUSE_REQUEST_RESUPPLY,
                WAREHOUSE_REQUEST_RESUPPLY,
            ]
        }
    )
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 3)

    count = await _count_active_orders(session, "warehouse-002", "cimento", "factory-003")
    assert count == 1, (
        f"Warehouse→factory dedup failed: {count} active orders "
        f"(request_resupply should be idempotent)"
    )


async def test_factory_send_stock_idempotent(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client

    await session.execute(
        text("UPDATE warehouse_stocks SET stock=0 WHERE warehouse_id='warehouse-002' AND material_id='cimento'")
    )
    await session.commit()

    llm_wh = make_entity_routing_llm(**{"warehouse-002": [WAREHOUSE_REQUEST_RESUPPLY]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_wh):
        await advance_ticks_with_settle(client, 1)

    llm_factory = make_entity_routing_llm(
        **{"factory-003": [FACTORY_SEND_STOCK, FACTORY_SEND_STOCK, FACTORY_SEND_STOCK]}
    )
    with patch("src.agents.base.ChatOpenAI", return_value=llm_factory):
        await advance_ticks_with_settle(client, 3)

    count = await _count_active_orders(session, "warehouse-002", "cimento", "factory-003")
    assert count == 1, (
        f"Factory send_stock idempotency failed: {count} active orders"
    )

    reserved = (await session.execute(
        text(
            "SELECT stock_reserved FROM factory_products "
            "WHERE factory_id='factory-003' AND material_id='cimento'"
        )
    )).scalar_one()
    assert float(reserved) == 100.0, (
        f"Factory must reserve exactly 100 ton once; got {reserved} "
        f"(double-reservation would push this to 200)"
    )
