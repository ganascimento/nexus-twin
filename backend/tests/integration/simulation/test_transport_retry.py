import json
from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    make_llm_responses,
)

pytestmark = pytest.mark.asyncio


async def _set_all_trucks_busy(session) -> None:
    await session.execute(
        text("UPDATE trucks SET status='in_transit' WHERE status='idle'")
    )


async def _set_truck_idle(session, truck_id: str) -> None:
    await session.execute(
        text(
            "UPDATE trucks SET status='idle', maintenance_start_tick=NULL, "
            "maintenance_duration_ticks=NULL, active_route_id=NULL, cargo=NULL "
            "WHERE id=:tid"
        ),
        {"tid": truck_id},
    )


async def _create_confirmed_order(
    session,
    *,
    requester_id: str,
    target_id: str,
    material_id: str,
    quantity_tons: float,
) -> str:
    result = await session.execute(
        text(
            "INSERT INTO pending_orders "
            "(id, requester_type, requester_id, target_type, target_id, material_id, quantity_tons, status, age_ticks) "
            "VALUES (gen_random_uuid(), 'store', :rid, 'warehouse', :tid, :mid, :qty, 'confirmed', 0) "
            "RETURNING id"
        ),
        {"rid": requester_id, "tid": target_id, "mid": material_id, "qty": quantity_tons},
    )
    return str(result.scalar_one())


async def _get_order_status(session, order_id: str) -> str | None:
    result = await session.execute(
        text("SELECT status FROM pending_orders WHERE id=:oid"),
        {"oid": order_id},
    )
    return result.scalar_one_or_none()


async def _count_routes_for_order(session, order_id: str) -> int:
    result = await session.execute(
        text("SELECT COUNT(*) FROM routes WHERE order_id=:oid"),
        {"oid": order_id},
    )
    return int(result.scalar_one())


async def _count_truck_events_for_order(session, order_id: str) -> int:
    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM events "
            "WHERE entity_type='truck' AND payload->>'order_id' = :oid"
        ),
        {"oid": order_id},
    )
    return int(result.scalar_one())


async def test_transport_retry_when_no_truck(seeded_simulation_client, mock_valhalla):
    client, session, mock_redis = seeded_simulation_client

    await _set_all_trucks_busy(session)
    order_id = await _create_confirmed_order(
        session,
        requester_id="store-001",
        target_id="warehouse-002",
        material_id="cimento",
        quantity_tons=15.0,
    )
    await session.commit()

    hold_llm = make_llm_responses({
        "action": "hold",
        "payload": None,
        "reasoning_summary": "No action",
    })
    with patch("src.agents.base.ChatOpenAI", return_value=hold_llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    assert await _get_order_status(session, order_id) == "confirmed"
    assert await _count_routes_for_order(session, order_id) == 0
    assert await _count_truck_events_for_order(session, order_id) == 0

    await _set_truck_idle(session, "truck-004")
    await session.commit()

    with patch("src.agents.base.ChatOpenAI", return_value=hold_llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()

    result = await session.execute(
        text(
            "SELECT event_type, entity_id FROM events "
            "WHERE entity_type='truck' AND payload->>'order_id' = :oid"
        ),
        {"oid": order_id},
    )
    events = result.all()
    assert len(events) >= 1, "Transport retry must dispatch a truck event for confirmed order"
    event_types = {row[0] for row in events}
    assert "contract_proposal" in event_types or "new_order" in event_types

    accept_truck_id = events[0][1]
    accept_llm = make_llm_responses({
        "action": "accept_contract",
        "payload": {"order_id": order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accept",
    })
    with patch("src.agents.base.ChatOpenAI", return_value=accept_llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    assert await _count_routes_for_order(session, order_id) >= 1, (
        "After acceptance a route must exist for the original order_id"
    )
    truck_status = (await session.execute(
        text("SELECT status FROM trucks WHERE id=:tid"), {"tid": accept_truck_id}
    )).scalar_one()
    assert truck_status == "in_transit"


async def test_confirmed_order_not_lost(seeded_simulation_client, mock_valhalla):
    client, session, mock_redis = seeded_simulation_client

    await _set_all_trucks_busy(session)
    order_id = await _create_confirmed_order(
        session,
        requester_id="store-001",
        target_id="warehouse-002",
        material_id="cimento",
        quantity_tons=15.0,
    )
    await session.execute(
        text(
            "UPDATE warehouse_stocks SET stock_reserved=30.0 "
            "WHERE warehouse_id='warehouse-002' AND material_id='cimento'"
        )
    )
    await session.commit()

    hold_llm = make_llm_responses(
        *[
            {"action": "hold", "payload": None, "reasoning_summary": "No action"}
            for _ in range(30)
        ]
    )
    total_ticks = 5
    with patch("src.agents.base.ChatOpenAI", return_value=hold_llm):
        for _ in range(total_ticks):
            await advance_ticks_with_settle(client, 1)
            await session.rollback()
            reserved = (await session.execute(
                text(
                    "SELECT stock_reserved FROM warehouse_stocks "
                    "WHERE warehouse_id='warehouse-002' AND material_id='cimento'"
                )
            )).scalar_one()
            assert float(reserved) == 30.0

    await session.rollback()
    status = await _get_order_status(session, order_id)
    assert status == "confirmed"
    assert await _count_routes_for_order(session, order_id) == 0
