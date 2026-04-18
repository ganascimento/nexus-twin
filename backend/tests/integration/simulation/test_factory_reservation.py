from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    make_combined_routing_llm,
    make_entity_routing_llm,
)

pytestmark = pytest.mark.asyncio


async def _empty_warehouse(session):
    await session.execute(
        text("UPDATE warehouse_stocks SET stock=0 WHERE warehouse_id='warehouse-002' AND material_id='cimento'")
    )
    await session.commit()


async def _factory_reserved(session, factory_id, material_id) -> float:
    result = await session.execute(
        text(
            "SELECT stock_reserved FROM factory_products "
            "WHERE factory_id=:fid AND material_id=:mid"
        ),
        {"fid": factory_id, "mid": material_id},
    )
    return float(result.scalar_one())


async def _factory_stock(session, factory_id, material_id) -> float:
    result = await session.execute(
        text(
            "SELECT stock FROM factory_products "
            "WHERE factory_id=:fid AND material_id=:mid"
        ),
        {"fid": factory_id, "mid": material_id},
    )
    return float(result.scalar_one())


async def _run_until_factory_order_exists(client, session):
    request_resupply = {
        "action": "request_resupply",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 100.0,
            "from_factory_id": "factory-003",
        },
        "reasoning_summary": "Empty",
    }
    llm_t1 = make_entity_routing_llm(**{"warehouse-002": [request_resupply]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t1):
        await advance_ticks_with_settle(client, 1)

    send_stock = {
        "action": "send_stock",
        "payload": {
            "material_id": "cimento",
            "quantity_tons": 100.0,
            "destination_warehouse_id": "warehouse-002",
        },
        "reasoning_summary": "Send",
    }
    llm_t2 = make_entity_routing_llm(**{"factory-003": [send_stock]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t2):
        await advance_ticks_with_settle(client, 1)

    result = await session.execute(
        text(
            "SELECT id FROM pending_orders "
            "WHERE requester_id='warehouse-002' AND target_id='factory-003' "
            "AND material_id='cimento' ORDER BY created_at DESC LIMIT 1"
        )
    )
    row = result.first()
    assert row is not None
    return str(row.id)


async def test_factory_reserves_on_send_stock(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _empty_warehouse(session)

    reserved_before = await _factory_reserved(session, "factory-003", "cimento")
    assert reserved_before == 0.0

    await _run_until_factory_order_exists(client, session)

    reserved_after_send = await _factory_reserved(session, "factory-003", "cimento")
    assert reserved_after_send == 100.0, (
        f"Expected factory.stock_reserved=100 after send_stock, got {reserved_after_send}"
    )


async def test_factory_stock_reserved_zero_after_delivery(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _empty_warehouse(session)

    order_id = await _run_until_factory_order_exists(client, session)

    truck_accept = {
        "action": "accept_contract",
        "payload": {"order_id": order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accept",
    }
    llm_t3 = make_combined_routing_llm(by_agent={"truck": [truck_accept]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t3):
        await advance_ticks_with_settle(client, 1)

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 6)

    reserved_final = await _factory_reserved(session, "factory-003", "cimento")
    assert reserved_final == 0.0, (
        f"stock_reserved must return to 0 after delivery; got {reserved_final}"
    )
    assert reserved_final >= 0.0, (
        f"stock_reserved must NEVER be negative; got {reserved_final}"
    )


async def test_factory_stock_decremented_by_exact_quantity(seeded_simulation_client, mock_valhalla):
    client, session, _ = seeded_simulation_client
    await _empty_warehouse(session)

    initial_stock = await _factory_stock(session, "factory-003", "cimento")

    order_id = await _run_until_factory_order_exists(client, session)

    truck_accept = {
        "action": "accept_contract",
        "payload": {"order_id": order_id, "chosen_route_risk_level": "low"},
        "reasoning_summary": "Accept",
    }
    llm_t3 = make_combined_routing_llm(by_agent={"truck": [truck_accept]})
    with patch("src.agents.base.ChatOpenAI", return_value=llm_t3):
        await advance_ticks_with_settle(client, 1)

    llm_hold = make_combined_routing_llm()
    with patch("src.agents.base.ChatOpenAI", return_value=llm_hold):
        await advance_ticks_with_settle(client, 6)

    final_stock = await _factory_stock(session, "factory-003", "cimento")
    assert final_stock == initial_stock - 100.0, (
        f"Expected factory.stock == {initial_stock - 100.0} after delivery, got {final_stock}"
    )
