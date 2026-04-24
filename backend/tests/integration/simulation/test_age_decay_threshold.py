import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    make_combined_routing_llm,
    make_entity_routing_llm,
)

pytestmark = pytest.mark.asyncio


async def _seed_aged_confirmed_order(session, age_ticks: int) -> str:
    await session.execute(
        text(
            "UPDATE warehouse_stocks SET stock=500, stock_reserved=0 "
            "WHERE warehouse_id='warehouse-002'"
        )
    )
    await session.execute(
        text(
            "UPDATE warehouse_stocks SET stock_reserved=5 "
            "WHERE warehouse_id='warehouse-002' AND material_id='cimento'"
        )
    )
    order_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO pending_orders (id, requester_type, requester_id, "
            "target_type, target_id, material_id, quantity_tons, status, age_ticks) "
            "VALUES (:id, 'store', 'store-001', 'warehouse', 'warehouse-002', "
            "'cimento', 5.0, 'confirmed', :age)"
        ),
        {"id": str(order_id), "age": age_ticks},
    )
    await session.commit()
    return str(order_id)


async def test_orphan_loop_emits_max_age_ticks_equal_to_aged_order(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client
    order_id = await _seed_aged_confirmed_order(session, age_ticks=9)

    with patch("src.agents.base.ChatOpenAI", return_value=make_combined_routing_llm()):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    event = (await session.execute(
        text(
            "SELECT payload FROM events "
            "WHERE event_type='contract_proposal' AND entity_type='truck' "
            "AND status IN ('active','resolved') "
            "ORDER BY created_at DESC LIMIT 1"
        )
    )).first()
    assert event is not None, "orphan loop must have dispatched a contract_proposal"

    payload = event.payload
    # age_ticks was 9 at seed, plus +1 from engine tick before dispatch, expect ≥ 9.
    assert payload.get("max_age_ticks") is not None
    assert payload["max_age_ticks"] >= 9
    manifest = payload.get("orders_manifest")
    assert isinstance(manifest, list)
    assert any(m["order_id"] == order_id for m in manifest)


async def test_handler_level_dispatch_includes_max_age_ticks(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
    await session.execute(
        text("UPDATE store_stocks SET stock=1000 WHERE store_id='store-001' AND material_id != 'cimento'")
    )
    await session.commit()

    store_order = {
        "action": "order_replenishment",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 15.0,
            "from_warehouse_id": "warehouse-002",
        },
        "reasoning_summary": "Low",
    }
    with patch(
        "src.agents.base.ChatOpenAI",
        return_value=make_entity_routing_llm(**{"store-001": [store_order]}),
    ):
        await advance_ticks_with_settle(client, 1)

    order_row = (await session.execute(
        text(
            "SELECT id FROM pending_orders "
            "WHERE requester_id='store-001' AND material_id='cimento' "
            "ORDER BY created_at DESC LIMIT 1"
        )
    )).first()
    assert order_row is not None
    order_id = str(order_row.id)

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

    await session.rollback()
    event = (await session.execute(
        text(
            "SELECT payload FROM events "
            "WHERE event_type='contract_proposal' AND entity_type='truck' "
            "AND payload->>'order_id' = :oid "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"oid": order_id},
    )).first()
    assert event is not None
    payload = event.payload
    assert "max_age_ticks" in payload
    assert payload["max_age_ticks"] >= 0
    manifest = payload.get("orders_manifest")
    assert isinstance(manifest, list)
    assert manifest[0]["order_id"] == order_id
    assert manifest[0]["material_id"] == "cimento"
    assert manifest[0]["quantity_tons"] == 15.0
