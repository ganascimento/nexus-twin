import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    get_stock,
    make_combined_routing_llm,
)

pytestmark = pytest.mark.asyncio


HOLD = {"action": "hold", "payload": None, "reasoning_summary": "no-op"}


async def _get_warehouse_stock(session, wh_id: str, material_id: str) -> tuple[float, float]:
    row = (await session.execute(
        text(
            "SELECT stock, stock_reserved FROM warehouse_stocks "
            "WHERE warehouse_id=:wid AND material_id=:mid"
        ),
        {"wid": wh_id, "mid": material_id},
    )).first()
    return (float(row.stock), float(row.stock_reserved))


async def _seed_two_confirmed_orders_same_route(session):
    await session.execute(
        text(
            "UPDATE warehouse_stocks SET stock=500, stock_reserved=0 "
            "WHERE warehouse_id='warehouse-002'"
        )
    )
    # Reserve stock upfront for the two confirmed orders we will seed.
    await session.execute(
        text(
            "UPDATE warehouse_stocks SET stock_reserved=5 "
            "WHERE warehouse_id='warehouse-002' AND material_id='cimento'"
        )
    )
    await session.execute(
        text(
            "UPDATE warehouse_stocks SET stock_reserved=3 "
            "WHERE warehouse_id='warehouse-002' AND material_id='vergalhao'"
        )
    )

    order_a = uuid.uuid4()
    order_b = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO pending_orders "
            "(id, requester_type, requester_id, target_type, target_id, "
            " material_id, quantity_tons, status, age_ticks) "
            "VALUES (:id, 'store', 'store-001', 'warehouse', 'warehouse-002', "
            " 'cimento', 5.0, 'confirmed', 2)"
        ),
        {"id": str(order_a)},
    )
    await session.execute(
        text(
            "INSERT INTO pending_orders "
            "(id, requester_type, requester_id, target_type, target_id, "
            " material_id, quantity_tons, status, age_ticks) "
            "VALUES (:id, 'store', 'store-001', 'warehouse', 'warehouse-002', "
            " 'vergalhao', 3.0, 'confirmed', 7)"
        ),
        {"id": str(order_b)},
    )
    await session.commit()
    return str(order_a), str(order_b)


async def test_orphan_loop_bundles_sibling_orders_into_single_contract(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client
    order_a, order_b = await _seed_two_confirmed_orders_same_route(session)

    with patch("src.agents.base.ChatOpenAI", return_value=make_combined_routing_llm()):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()

    events = (await session.execute(
        text(
            "SELECT entity_id, payload FROM events "
            "WHERE event_type='contract_proposal' AND entity_type='truck' "
            "AND status IN ('active', 'resolved') "
            "ORDER BY created_at DESC"
        )
    )).all()

    matching = [
        e for e in events
        if e.payload
        and isinstance(e.payload.get("orders_manifest"), list)
        and {m["order_id"] for m in e.payload["orders_manifest"]} >= {order_a, order_b}
    ]
    assert len(matching) == 1, (
        f"Expected exactly one bundled contract_proposal containing both orders; "
        f"found {len(matching)} events"
    )
    payload = matching[0].payload
    assert payload["quantity_tons"] == pytest.approx(8.0)
    assert payload["max_age_ticks"] >= 7


async def test_bundled_contract_accepted_then_delivered_applies_all_materials(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client
    order_a, order_b = await _seed_two_confirmed_orders_same_route(session)

    # Freeze demand at zero so stock deltas track delivery only, not consumption.
    await session.execute(
        text(
            "UPDATE store_stocks SET demand_rate=0 "
            "WHERE store_id='store-001' AND material_id IN ('cimento','vergalhao')"
        )
    )
    await session.commit()

    initial_cimento = await get_stock(session, "store_stocks", "store_id", "store-001", "cimento")
    initial_vergalhao = await get_stock(session, "store_stocks", "store_id", "store-001", "vergalhao")

    # Tick 1: orphan loop dispatches bundled contract_proposal.
    with patch("src.agents.base.ChatOpenAI", return_value=make_combined_routing_llm()):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    event_row = (await session.execute(
        text(
            "SELECT entity_id, payload FROM events "
            "WHERE event_type='contract_proposal' AND entity_type='truck' "
            "ORDER BY created_at DESC LIMIT 1"
        )
    )).first()
    assert event_row is not None
    truck_id = event_row.entity_id

    manifest_from_event = event_row.payload["orders_manifest"]
    accept = {
        "action": "accept_contract",
        "payload": {
            "order_id": order_a,
            "chosen_route_risk_level": "low",
            "orders_manifest": manifest_from_event,
        },
        "reasoning_summary": "Accept bundled",
    }
    with patch(
        "src.agents.base.ChatOpenAI",
        return_value=make_combined_routing_llm(by_agent={"truck": [accept]}),
    ):
        await advance_ticks_with_settle(client, 1)

    # Both orders must now be in_transit (not confirmed, not delivered yet).
    await session.rollback()
    statuses = (await session.execute(
        text("SELECT id, status FROM pending_orders WHERE id IN (:a, :b)"),
        {"a": order_a, "b": order_b},
    )).all()
    status_by_id = {str(r.id): r.status for r in statuses}
    assert status_by_id[order_a] == "in_transit"
    assert status_by_id[order_b] == "in_transit"

    # Advance enough ticks for pickup + delivery to complete.
    with patch("src.agents.base.ChatOpenAI", return_value=make_combined_routing_llm()):
        await advance_ticks_with_settle(client, 20)

    await session.rollback()

    final_statuses = (await session.execute(
        text("SELECT id, status FROM pending_orders WHERE id IN (:a, :b)"),
        {"a": order_a, "b": order_b},
    )).all()
    final_status_by_id = {str(r.id): r.status for r in final_statuses}
    assert final_status_by_id[order_a] == "delivered"
    assert final_status_by_id[order_b] == "delivered"

    final_cimento = await get_stock(session, "store_stocks", "store_id", "store-001", "cimento")
    final_vergalhao = await get_stock(session, "store_stocks", "store_id", "store-001", "vergalhao")
    assert float(final_cimento) == pytest.approx(float(initial_cimento) + 5.0)
    assert float(final_vergalhao) == pytest.approx(float(initial_vergalhao) + 3.0)


async def test_orphan_loop_does_not_bundle_across_different_destinations(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    await session.execute(
        text("UPDATE warehouse_stocks SET stock=500, stock_reserved=0 WHERE warehouse_id='warehouse-002'")
    )
    await session.execute(
        text("UPDATE warehouse_stocks SET stock_reserved=5 WHERE warehouse_id='warehouse-002' AND material_id='cimento'")
    )
    await session.execute(
        text("UPDATE warehouse_stocks SET stock_reserved=3 WHERE warehouse_id='warehouse-002' AND material_id='vergalhao'")
    )

    order_a = uuid.uuid4()
    order_b = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO pending_orders (id, requester_type, requester_id, "
            "target_type, target_id, material_id, quantity_tons, status, age_ticks) "
            "VALUES (:id, 'store', 'store-001', 'warehouse', 'warehouse-002', "
            "'cimento', 5.0, 'confirmed', 2)"
        ),
        {"id": str(order_a)},
    )
    await session.execute(
        text(
            "INSERT INTO pending_orders (id, requester_type, requester_id, "
            "target_type, target_id, material_id, quantity_tons, status, age_ticks) "
            "VALUES (:id, 'store', 'store-002', 'warehouse', 'warehouse-002', "
            "'vergalhao', 3.0, 'confirmed', 2)"
        ),
        {"id": str(order_b)},
    )
    await session.commit()

    with patch("src.agents.base.ChatOpenAI", return_value=make_combined_routing_llm()):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()

    events = (await session.execute(
        text(
            "SELECT payload FROM events "
            "WHERE event_type='contract_proposal' AND entity_type='truck'"
        )
    )).all()

    bundled = [
        e for e in events
        if e.payload
        and isinstance(e.payload.get("orders_manifest"), list)
        and {m["order_id"] for m in e.payload["orders_manifest"]} == {str(order_a), str(order_b)}
    ]
    assert bundled == [], (
        "Orders for store-001 and store-002 must not be bundled (different destinations)"
    )
