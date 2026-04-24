from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    get_order_status,
    get_stock,
    get_stock_reserved,
    make_combined_routing_llm,
    make_entity_routing_llm,
    make_llm_responses,
)

pytestmark = pytest.mark.asyncio


HOLD = {"action": "hold", "payload": None, "reasoning_summary": "no-op"}


async def _empty_warehouse(session, warehouse_id: str, material_id: str):
    await session.execute(
        text(
            "UPDATE warehouse_stocks SET stock=0 "
            "WHERE warehouse_id=:wid AND material_id=:mid"
        ),
        {"wid": warehouse_id, "mid": material_id},
    )


async def _empty_factory(session, factory_id: str, material_id: str):
    await session.execute(
        text(
            "UPDATE factory_products SET stock=0, production_rate_current=0 "
            "WHERE factory_id=:fid AND material_id=:mid"
        ),
        {"fid": factory_id, "mid": material_id},
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


async def test_stop_production_does_not_affect_in_transit_order(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    await _empty_warehouse(session, "warehouse-002", "cimento")
    await session.commit()

    warehouse_resupply = {
        "action": "request_resupply",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 100.0,
            "from_factory_id": "factory-003",
        },
        "reasoning_summary": "Empty",
    }
    llm1 = make_entity_routing_llm(**{"warehouse-002": [warehouse_resupply]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm1):
        await advance_ticks_with_settle(client, 1)

    factory_send = {
        "action": "send_stock",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 100.0,
            "destination_warehouse_id": "warehouse-002",
        },
        "reasoning_summary": "Send",
    }
    llm2 = make_entity_routing_llm(**{"factory-003": [factory_send]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm2):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    order_id = await _fetch_latest_order_id(
        session, "warehouse-002", "cimento", target_id="factory-003"
    )
    assert order_id is not None

    truck_accept = {
        "action": "accept_contract",
        "payload": {"order_id": order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accept",
    }
    llm3 = make_combined_routing_llm(by_agent={"truck": [truck_accept]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm3):
        await advance_ticks_with_settle(client, 1)

    # Factory decides to stop producing mid-flight.
    factory_stop = {
        "action": "stop_production",
        "payload": {"material_id": "cimento"},
        "reasoning_summary": "Stop",
    }
    llm4 = make_entity_routing_llm(**{"factory-003": [factory_stop]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm4):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    production_rate = (await session.execute(
        text(
            "SELECT production_rate_current FROM factory_products "
            "WHERE factory_id='factory-003' AND material_id='cimento'"
        )
    )).scalar_one()
    assert float(production_rate) == 0.0

    order_status_mid = await get_order_status(session, order_id)
    assert order_status_mid == "in_transit"

    hold_llm = make_llm_responses(*([HOLD] * 30))
    with patch("src.agents.base.ChatOpenAI", return_value=hold_llm):
        await advance_ticks_with_settle(client, 6)

    await session.rollback()
    assert await get_order_status(session, order_id) == "delivered"

    factory_reserved = (await session.execute(
        text(
            "SELECT stock_reserved FROM factory_products "
            "WHERE factory_id='factory-003' AND material_id='cimento'"
        )
    )).scalar_one()
    assert float(factory_reserved) == 0.0
    assert float(factory_reserved) >= 0.0

    warehouse_stock = await get_stock(
        session, "warehouse_stocks", "warehouse_id", "warehouse-002", "cimento"
    )
    assert float(warehouse_stock) == 100.0


async def test_stop_production_rejects_new_resupply_from_empty_factory(
    seeded_simulation_client, mock_valhalla
):
    client, session, _ = seeded_simulation_client

    await _empty_warehouse(session, "warehouse-002", "cimento")
    await _empty_factory(session, "factory-003", "cimento")
    await session.commit()

    warehouse_resupply = {
        "action": "request_resupply",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 100.0,
            "from_factory_id": "factory-003",
        },
        "reasoning_summary": "Empty",
    }
    llm1 = make_entity_routing_llm(**{"warehouse-002": [warehouse_resupply]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm1):
        await advance_ticks_with_settle(client, 1)

    factory_send = {
        "action": "send_stock",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 100.0,
            "destination_warehouse_id": "warehouse-002",
        },
        "reasoning_summary": "Send",
    }
    llm2 = make_entity_routing_llm(**{"factory-003": [factory_send]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm2):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    factory_reserved = (await session.execute(
        text(
            "SELECT stock_reserved FROM factory_products "
            "WHERE factory_id='factory-003' AND material_id='cimento'"
        )
    )).scalar_one()
    assert float(factory_reserved) == 0.0

    confirmed_orders = (await session.execute(
        text(
            "SELECT COUNT(*) FROM pending_orders "
            "WHERE requester_id='warehouse-002' AND target_id='factory-003' "
            "AND material_id='cimento' AND status='confirmed'"
        )
    )).scalar_one()
    assert int(confirmed_orders) == 0
