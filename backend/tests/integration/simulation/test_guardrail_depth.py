import json
from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    get_order_status,
    get_stock_reserved,
    make_combined_routing_llm,
    make_entity_routing_llm,
    make_llm_responses,
)

pytestmark = pytest.mark.asyncio


HOLD = {"action": "hold", "payload": None, "reasoning_summary": "no-op"}


async def _set_low_store_stock(session, store_id: str, material_id: str, stock: float):
    await session.execute(
        text(
            "UPDATE store_stocks SET stock=:s "
            "WHERE store_id=:sid AND material_id=:mid"
        ),
        {"s": stock, "sid": store_id, "mid": material_id},
    )


async def _insert_pending_order(
    session,
    *,
    requester_type: str,
    requester_id: str,
    target_type: str,
    target_id: str,
    material_id: str,
    quantity_tons: float,
    status: str = "pending",
) -> str:
    result = await session.execute(
        text(
            "INSERT INTO pending_orders "
            "(id, requester_type, requester_id, target_type, target_id, "
            " material_id, quantity_tons, status, age_ticks) "
            "VALUES (gen_random_uuid(), :rt, :rid, :tt, :tid, :mid, :qty, :st, 0) "
            "RETURNING id"
        ),
        {
            "rt": requester_type, "rid": requester_id,
            "tt": target_type, "tid": target_id,
            "mid": material_id, "qty": quantity_tons,
            "st": status,
        },
    )
    return str(result.scalar_one())


async def test_confirm_order_with_wrong_warehouse_is_rejected(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    # Order is targeted to warehouse-001, but warehouse-002 will try to confirm it.
    order_id = await _insert_pending_order(
        session,
        requester_type="store", requester_id="store-001",
        target_type="warehouse", target_id="warehouse-001",
        material_id="cimento", quantity_tons=30.0,
    )
    await session.commit()

    wrong_confirm = {
        "action": "confirm_order",
        "payload": {"order_id": order_id, "quantity_tons": 30.0, "eta_ticks": 3},
        "reasoning_summary": "Wrong warehouse tries to confirm",
    }
    # warehouse-001 has 100 cimento in seed — trigger would fire for warehouse-001,
    # so we only program warehouse-002 to inject a bogus confirm and hold for the others.
    llm = make_combined_routing_llm(
        by_entity={"warehouse-002": [wrong_confirm]},
        by_agent={"warehouse": [HOLD], "store": [HOLD], "factory": [HOLD], "truck": [HOLD]},
    )
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    reserved_001 = await get_stock_reserved(session, "warehouse-001", "cimento")
    reserved_002 = await get_stock_reserved(session, "warehouse-002", "cimento")
    assert reserved_001 is not None and float(reserved_001) == 0.0
    assert reserved_002 is not None and float(reserved_002) == 0.0


async def test_accept_contract_for_delivered_order_is_noop(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    order_id = await _insert_pending_order(
        session,
        requester_type="store", requester_id="store-001",
        target_type="warehouse", target_id="warehouse-002",
        material_id="cimento", quantity_tons=30.0,
        status="delivered",
    )

    # Inject a contract_proposal event for truck-004 to wake it up.
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
        "reasoning_summary": "Attempt accept on delivered order",
    }
    llm = make_combined_routing_llm(
        by_entity={"truck-004": [truck_accept]},
        by_agent={"store": [HOLD], "warehouse": [HOLD], "factory": [HOLD]},
    )
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    truck_row = (await session.execute(
        text("SELECT status, active_route_id, cargo FROM trucks WHERE id='truck-004'")
    )).first()
    assert truck_row is not None
    assert truck_row.status == "idle"
    assert truck_row.active_route_id is None
    assert truck_row.cargo is None

    routes_for_order = (await session.execute(
        text("SELECT COUNT(*) FROM routes WHERE order_id=:oid"),
        {"oid": order_id},
    )).scalar_one()
    assert int(routes_for_order) == 0

    status = await get_order_status(session, order_id)
    assert status == "delivered"


async def test_send_stock_with_wrong_material_fails_cleanly(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    # factory-003 only produces cimento. Tell it to send 'vergalhao' — which it does not produce.
    warehouse_resupply = {
        "action": "request_resupply",
        "payload": {
            "material_id": "vergalhao",
            "quantity_tons": 50.0,
            "from_factory_id": "factory-003",
        },
        "reasoning_summary": "Ask for vergalhao from cimento factory",
    }
    llm1 = make_entity_routing_llm(**{"warehouse-002": [warehouse_resupply]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm1):
        await advance_ticks_with_settle(client, 1)

    factory_send = {
        "action": "send_stock",
        "payload": {
            "material_id": "vergalhao",
            "quantity_tons": 50.0,
            "destination_warehouse_id": "warehouse-002",
        },
        "reasoning_summary": "Send wrong material",
    }
    llm2 = make_entity_routing_llm(**{"factory-003": [factory_send]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm2):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    confirmed = (await session.execute(
        text(
            "SELECT COUNT(*) FROM pending_orders "
            "WHERE target_id='factory-003' AND material_id='vergalhao' "
            "AND status='confirmed'"
        )
    )).scalar_one()
    assert int(confirmed) == 0

    # factory-003 does not have a vergalhao row — no reserve can be made.
    vergalhao_row = (await session.execute(
        text(
            "SELECT stock_reserved FROM factory_products "
            "WHERE factory_id='factory-003' AND material_id='vergalhao'"
        )
    )).first()
    assert vergalhao_row is None


async def test_warehouse_agent_crash_does_not_leave_stock_reserved(
    seeded_simulation_client, mock_valhalla, monkeypatch
):
    client, session, _ = seeded_simulation_client

    await _set_low_store_stock(session, "store-001", "cimento", 1.0)
    order_id = await _insert_pending_order(
        session,
        requester_type="store", requester_id="store-001",
        target_type="warehouse", target_id="warehouse-002",
        material_id="cimento", quantity_tons=30.0,
    )
    await session.commit()

    import src.services.decision_effect_processor as dep_module

    async def _boom(self, entity_id, payload, tick):
        raise RuntimeError("simulated crash in confirm_order handler")

    monkeypatch.setattr(
        dep_module.DecisionEffectProcessor,
        "_handle_confirm_order",
        _boom,
    )

    warehouse_confirm = {
        "action": "confirm_order",
        "payload": {"order_id": order_id, "quantity_tons": 30.0, "eta_ticks": 3},
        "reasoning_summary": "Confirm",
    }
    llm = make_combined_routing_llm(
        by_entity={"warehouse-002": [warehouse_confirm]},
        by_agent={"store": [HOLD], "factory": [HOLD], "truck": [HOLD]},
    )
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    reserved = await get_stock_reserved(session, "warehouse-002", "cimento")
    assert reserved is not None
    assert float(reserved) == 0.0

    status = await get_order_status(session, order_id)
    # Order must not be confirmed if the effect handler crashed.
    assert status != "confirmed"


async def test_partial_effect_rolled_back_on_exception(
    seeded_simulation_client, mock_valhalla, monkeypatch
):
    client, session, _ = seeded_simulation_client

    await _set_low_store_stock(session, "store-001", "cimento", 1.0)
    order_id = await _insert_pending_order(
        session,
        requester_type="store", requester_id="store-001",
        target_type="warehouse", target_id="warehouse-002",
        material_id="cimento", quantity_tons=30.0,
    )
    await session.commit()

    import src.services.decision_effect_processor as dep_module

    async def _boom_after_confirm(self, order, warehouse_id, tick):
        raise RuntimeError("simulated crash while dispatching truck")

    monkeypatch.setattr(
        dep_module.DecisionEffectProcessor,
        "_dispatch_truck_for_order",
        _boom_after_confirm,
    )

    warehouse_confirm = {
        "action": "confirm_order",
        "payload": {"order_id": order_id, "quantity_tons": 30.0, "eta_ticks": 3},
        "reasoning_summary": "Confirm",
    }
    llm = make_combined_routing_llm(
        by_entity={"warehouse-002": [warehouse_confirm]},
        by_agent={"store": [HOLD], "factory": [HOLD], "truck": [HOLD]},
    )
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    reserved = await get_stock_reserved(session, "warehouse-002", "cimento")
    assert reserved is not None
    assert float(reserved) == 0.0

    status = await get_order_status(session, order_id)
    assert status == "pending"


# ---------------------------------------------------------------------------
# Effect processor edge cases — untested code paths
# ---------------------------------------------------------------------------


async def test_accept_contract_route_computation_failure(
    seeded_simulation_client,
):
    from unittest.mock import AsyncMock as AM

    client, session, _ = seeded_simulation_client

    order_id = await _insert_pending_order(
        session,
        requester_type="store", requester_id="store-001",
        target_type="warehouse", target_id="warehouse-002",
        material_id="cimento", quantity_tons=30.0,
        status="confirmed",
    )
    await session.execute(
        text(
            "INSERT INTO events (id, event_type, source, entity_type, entity_id, payload, status, tick_start) "
            "VALUES (gen_random_uuid(), 'contract_proposal', 'test', 'truck', 'truck-004', "
            "CAST(:payload AS JSONB), 'active', 0)"
        ),
        {"payload": json.dumps({"order_id": order_id})},
    )
    await session.commit()

    truck_accept = {
        "action": "accept_contract",
        "payload": {"order_id": order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accept",
    }
    llm = make_combined_routing_llm(
        by_entity={"truck-004": [truck_accept]},
        by_agent={"store": [HOLD], "warehouse": [HOLD], "factory": [HOLD]},
    )
    with patch("src.agents.base.ChatOpenAI", return_value=llm), \
         patch("src.services.route.RouteService.compute_route", new_callable=AM, side_effect=Exception("Valhalla offline")):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    truck = (await session.execute(
        text("SELECT status, active_route_id FROM trucks WHERE id='truck-004'")
    )).one()
    assert truck.status == "idle", "Truck must stay idle when route computation fails"
    assert truck.active_route_id is None, "No route must be assigned"

    routes = (await session.execute(
        text("SELECT COUNT(*) FROM routes WHERE order_id=:oid"), {"oid": order_id}
    )).scalar_one()
    assert int(routes) == 0, "No route must be created on Valhalla failure"


async def test_refuse_contract_no_alternate_truck(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    order_id = await _insert_pending_order(
        session,
        requester_type="store", requester_id="store-001",
        target_type="warehouse", target_id="warehouse-002",
        material_id="cimento", quantity_tons=30.0,
        status="confirmed",
    )
    await session.execute(
        text("UPDATE trucks SET status='in_transit' WHERE id <> 'truck-004'")
    )
    await session.execute(
        text(
            "INSERT INTO events (id, event_type, source, entity_type, entity_id, payload, status, tick_start) "
            "VALUES (gen_random_uuid(), 'contract_proposal', 'test', 'truck', 'truck-004', "
            "CAST(:payload AS JSONB), 'active', 0)"
        ),
        {"payload": json.dumps({"order_id": order_id})},
    )
    await session.commit()

    truck_refuse = {
        "action": "refuse_contract",
        "payload": {"order_id": order_id, "reason": "too far"},
        "reasoning_summary": "Refuse",
    }
    llm = make_combined_routing_llm(
        by_entity={"truck-004": [truck_refuse]},
        by_agent={"store": [HOLD], "warehouse": [HOLD], "factory": [HOLD]},
    )
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    new_proposals = (await session.execute(
        text(
            "SELECT COUNT(*) FROM events "
            "WHERE event_type='contract_proposal' AND entity_id <> 'truck-004' "
            "AND payload->>'order_id' = :oid"
        ),
        {"oid": order_id},
    )).scalar_one()
    assert int(new_proposals) == 0, (
        "No new contract_proposal must be created when no alternative truck is available"
    )

    status = await get_order_status(session, order_id)
    assert status == "confirmed", "Order must stay confirmed after refuse with no alternate truck"


async def test_alert_breakdown_truck_without_route(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    await session.execute(
        text(
            "UPDATE trucks SET status='broken', degradation=0.80, "
            "cargo=NULL, active_route_id=NULL WHERE id='truck-006'"
        )
    )
    await session.execute(
        text(
            "INSERT INTO events (id, event_type, source, entity_type, entity_id, payload, status, tick_start) "
            "VALUES (gen_random_uuid(), 'truck_breakdown', 'engine', 'truck', 'truck-006', "
            "CAST(:payload AS JSONB), 'active', 0)"
        ),
        {"payload": json.dumps({"reason": "degradation_threshold"})},
    )
    await session.commit()

    alert_response = {
        "action": "alert_breakdown",
        "payload": {"current_degradation": 0.80},
        "reasoning_summary": "Request rescue",
    }
    llm = make_combined_routing_llm(
        by_entity={"truck-006": [alert_response]},
        by_agent={"store": [HOLD], "warehouse": [HOLD], "factory": [HOLD]},
    )
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    rescue_events = (await session.execute(
        text(
            "SELECT entity_id, payload FROM events "
            "WHERE event_type='contract_proposal' "
            "AND payload->>'rescue_for' = 'truck-006'"
        )
    )).all()
    assert len(rescue_events) >= 1, (
        "Rescue event must be created even if broken truck has no active route"
    )
    assert rescue_events[0].entity_id != "truck-006", "Rescue must target a different truck"


async def test_send_stock_insufficient_factory_stock(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    await session.execute(
        text(
            "UPDATE factory_products SET stock=0, stock_reserved=0 "
            "WHERE factory_id='factory-003' AND material_id='cimento'"
        )
    )
    await session.commit()

    factory_send = {
        "action": "send_stock",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 100.0,
            "destination_warehouse_id": "warehouse-002",
        },
        "reasoning_summary": "Send from empty factory",
    }
    llm = make_entity_routing_llm(**{"factory-003": [factory_send]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    stock = (await session.execute(
        text(
            "SELECT stock, stock_reserved FROM factory_products "
            "WHERE factory_id='factory-003' AND material_id='cimento'"
        )
    )).one()
    assert float(stock.stock_reserved) == 0.0, (
        "Factory must not reserve stock when it has 0 available"
    )

    truck_events = (await session.execute(
        text(
            "SELECT COUNT(*) FROM events "
            "WHERE entity_type='truck' AND payload->>'origin_id' = 'factory-003'"
        )
    )).scalar_one()
    assert int(truck_events) == 0, (
        "No truck event must be created when factory has insufficient stock"
    )
