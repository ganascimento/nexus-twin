import json
from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    make_combined_routing_llm,
    make_entity_routing_llm,
    make_llm_responses,
    make_routing_llm,
)

pytestmark = pytest.mark.asyncio


HOLD = {"action": "hold", "payload": None, "reasoning_summary": "no-op"}


STORE_ORDER = {
    "action": "order_replenishment",
    "payload": {
        "material_id": "cimento",
        "quantity_tons": 30.0,
        "from_warehouse_id": "warehouse-002",
    },
    "reasoning_summary": "Stock below reorder point",
}


async def _set_low_store_stock(session, store_id: str, material_id: str, stock: float):
    await session.execute(
        text(
            "UPDATE store_stocks SET stock=:s "
            "WHERE store_id=:sid AND material_id=:mid"
        ),
        {"s": stock, "sid": store_id, "mid": material_id},
    )


async def _empty_warehouse_material(session, warehouse_id: str, material_id: str):
    await session.execute(
        text(
            "UPDATE warehouse_stocks SET stock=0 "
            "WHERE warehouse_id=:wid AND material_id=:mid"
        ),
        {"wid": warehouse_id, "mid": material_id},
    )


async def _fetch_latest_order_id(session, requester_id, material_id, target_id=None):
    where = "requester_id=:rid AND material_id=:mid"
    params = {"rid": requester_id, "mid": material_id}
    if target_id is not None:
        where += " AND target_id=:tid"
        params["tid"] = target_id
    result = await session.execute(
        text(
            f"SELECT id FROM pending_orders WHERE {where} "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        params,
    )
    row = result.first()
    return str(row.id) if row is not None else None


async def _assert_no_confirmed_without_reservation(session):
    rows = (await session.execute(
        text(
            "SELECT id, target_type, target_id, material_id, quantity_tons "
            "FROM pending_orders WHERE status='confirmed'"
        )
    )).all()
    for row in rows:
        if row.target_type == "warehouse":
            reserved = (await session.execute(
                text(
                    "SELECT stock_reserved FROM warehouse_stocks "
                    "WHERE warehouse_id=:wid AND material_id=:mid"
                ),
                {"wid": row.target_id, "mid": row.material_id},
            )).scalar_one_or_none()
        elif row.target_type == "factory":
            reserved = (await session.execute(
                text(
                    "SELECT stock_reserved FROM factory_products "
                    "WHERE factory_id=:fid AND material_id=:mid"
                ),
                {"fid": row.target_id, "mid": row.material_id},
            )).scalar_one_or_none()
        else:
            continue
        assert reserved is not None, (
            f"Confirmed order {row.id} references missing stock row "
            f"{row.target_type}/{row.target_id}/{row.material_id}"
        )
        assert float(reserved) >= float(row.quantity_tons), (
            f"Confirmed order {row.id} requires {row.quantity_tons} tons but "
            f"target has only {reserved} reserved"
        )


async def test_no_confirmed_order_without_stock_reserved(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    await _set_low_store_stock(session, "store-001", "cimento", 1.0)
    await session.commit()

    llm_t1 = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
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
    await _assert_no_confirmed_without_reservation(session)

    truck_accept = {
        "action": "accept_contract",
        "payload": {"order_id": order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accept",
    }
    llm_t3 = make_combined_routing_llm(by_agent={"truck": [truck_accept]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t3):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    await _assert_no_confirmed_without_reservation(session)

    hold_llm = make_llm_responses(*([HOLD] * 40))
    for _ in range(10):
        with patch("src.agents.base.ChatOpenAI", return_value=hold_llm):
            await advance_ticks_with_settle(client, 1)
        await session.rollback()
        await _assert_no_confirmed_without_reservation(session)


async def test_no_pending_order_with_retry_after_tick(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    await _empty_warehouse_material(session, "warehouse-002", "cimento")
    await _set_low_store_stock(session, "store-001", "cimento", 1.0)
    await session.commit()

    async def _assert_invariant():
        await session.rollback()
        count = (await session.execute(
            text(
                "SELECT COUNT(*) FROM pending_orders "
                "WHERE status='pending' AND retry_after_tick IS NOT NULL"
            )
        )).scalar_one()
        assert int(count) == 0, (
            "Found pending order with non-null retry_after_tick — "
            "inconsistent zombie state"
        )

    llm_t1 = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
        await advance_ticks_with_settle(client, 1)
    await _assert_invariant()

    order_id = await _fetch_latest_order_id(session, "store-001", "cimento")
    assert order_id is not None

    warehouse_reject = {
        "action": "reject_order",
        "payload": {
            "order_id": str(order_id),
            "reason": "insufficient_stock",
            "retry_after_ticks": 5,
        },
        "reasoning_summary": "No stock",
    }
    llm_t2 = make_routing_llm(warehouse=[warehouse_reject])
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t2):
        await advance_ticks_with_settle(client, 1)
    await _assert_invariant()

    hold_llm = make_llm_responses(*([HOLD] * 40))
    for _ in range(3):
        with patch("src.agents.base.ChatOpenAI", return_value=hold_llm):
            await advance_ticks_with_settle(client, 1)
        await _assert_invariant()

    retry_llm = make_entity_routing_llm(**{"store-001": [STORE_ORDER]})
    for _ in range(3):
        with patch("src.agents.base.ChatOpenAI", return_value=retry_llm):
            await advance_ticks_with_settle(client, 1)
        await _assert_invariant()


async def test_broken_truck_cannot_accept_contract(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    # Put truck-004 in broken state.
    await session.execute(
        text(
            "UPDATE trucks SET status='broken', cargo=NULL, active_route_id=NULL "
            "WHERE id='truck-004'"
        )
    )
    # Insert a pending_order and a contract_proposal event targeting the broken truck.
    order_row = await session.execute(
        text(
            "INSERT INTO pending_orders "
            "(id, requester_type, requester_id, target_type, target_id, "
            " material_id, quantity_tons, status, age_ticks) "
            "VALUES (gen_random_uuid(), 'store', 'store-001', 'warehouse', "
            "'warehouse-002', 'cimento', 30.0, 'confirmed', 0) "
            "RETURNING id"
        )
    )
    order_id = str(order_row.scalar_one())

    await session.execute(
        text(
            "INSERT INTO events ("
            "  id, event_type, source, entity_type, entity_id, payload, status, tick_start"
            ") VALUES ("
            "  gen_random_uuid(), 'contract_proposal', 'test', 'truck', 'truck-004', "
            "  CAST(:payload AS JSONB), 'active', 0"
            ")"
        ),
        {"payload": json.dumps({"order_id": order_id})},
    )
    await session.commit()

    truck_accept = {
        "action": "accept_contract",
        "payload": {"order_id": order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Attempt accept while broken",
    }
    llm = make_combined_routing_llm(
        by_entity={"truck-004": [truck_accept]},
        by_agent={"store": [HOLD], "warehouse": [HOLD], "factory": [HOLD]},
    )
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    truck_row = (await session.execute(
        text(
            "SELECT status, active_route_id, cargo FROM trucks WHERE id='truck-004'"
        )
    )).first()
    assert truck_row is not None
    assert truck_row.status == "broken"
    assert truck_row.active_route_id is None
    assert truck_row.cargo is None

    routes_for_order = (await session.execute(
        text("SELECT COUNT(*) FROM routes WHERE order_id=:oid"),
        {"oid": order_id},
    )).scalar_one()
    assert int(routes_for_order) == 0
