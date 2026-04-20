from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    get_order_status,
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
    "reasoning_summary": "Low",
}


async def _setup_confirmed_order_with_proposal(client, session):
    await session.execute(
        text("UPDATE store_stocks SET stock=1.0 WHERE store_id='store-001' AND material_id='cimento'")
    )
    await session.execute(
        text("UPDATE store_stocks SET stock=1000 WHERE store_id='store-001' AND material_id != 'cimento'")
    )
    await session.commit()

    llm_t1 = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
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
    llm_t2 = make_entity_routing_llm(**{"warehouse-002": [warehouse_confirm]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t2):
        await advance_ticks_with_settle(client, 1)

    event_row = (await session.execute(
        text(
            "SELECT entity_id FROM events "
            "WHERE entity_type='truck' AND event_type IN ('contract_proposal','new_order') "
            "AND payload->>'order_id' = :oid AND status='active' "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"oid": order_id},
    )).first()
    assert event_row is not None, "No contract_proposal was dispatched to a truck"
    return order_id, event_row.entity_id


async def test_refuse_dispatches_to_alternate_truck(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    order_id, first_truck = await _setup_confirmed_order_with_proposal(client, session)

    refuse_response = {
        "action": "refuse_contract",
        "payload": {"order_id": order_id, "reason": "route too risky"},
        "reasoning_summary": "Decline",
    }
    llm_t3 = make_entity_routing_llm(**{first_truck: [refuse_response]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t3):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    second_event = (await session.execute(
        text(
            "SELECT entity_id, created_at FROM events "
            "WHERE entity_type='truck' "
            "AND event_type IN ('contract_proposal','new_order') "
            "AND payload->>'order_id' = :oid "
            "AND entity_id <> :first_tid "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"oid": order_id, "first_tid": first_truck},
    )).first()
    assert second_event is not None, (
        f"After refuse, a new contract_proposal must be dispatched to a different truck; "
        f"first truck was {first_truck}"
    )
    assert second_event.entity_id != first_truck


async def test_refuse_leaves_order_confirmed(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    order_id, first_truck = await _setup_confirmed_order_with_proposal(client, session)

    status_before_refuse = await get_order_status(session, order_id)
    assert status_before_refuse == "confirmed"

    refuse_response = {
        "action": "refuse_contract",
        "payload": {"order_id": order_id, "reason": "route too risky"},
        "reasoning_summary": "Decline",
    }
    llm = make_entity_routing_llm(**{first_truck: [refuse_response]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    status_after_refuse = await get_order_status(session, order_id)
    assert status_after_refuse == "confirmed", (
        f"Order must stay confirmed between refuse and next-truck-accept; got {status_after_refuse}"
    )
