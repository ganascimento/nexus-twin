from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    make_entity_routing_llm,
)

pytestmark = pytest.mark.asyncio


async def _inject_chaos(client, event_type, entity_type, entity_id, payload=None, current_tick=0):
    body = {
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "payload": payload or {},
    }
    return await client.post(
        f"/chaos/events?current_tick={current_tick}", json=body
    )


async def _get_production_rate(session, factory_id, material_id):
    result = await session.execute(
        text(
            "SELECT production_rate_current FROM factory_products "
            "WHERE factory_id=:fid AND material_id=:mid"
        ),
        {"fid": factory_id, "mid": material_id},
    )
    row = result.scalar_one_or_none()
    return float(row) if row is not None else None


async def test_chaos_machine_breakdown_triggers_factory(seeded_simulation_client):
    client, session, _ = seeded_simulation_client

    resp = await _inject_chaos(
        client,
        event_type="machine_breakdown",
        entity_type="factory",
        entity_id="factory-001",
        payload={"material_id": "tijolos", "severity": "high"},
        current_tick=0,
    )
    assert resp.status_code == 201

    llm = make_entity_routing_llm(**{
        "factory-001": [{
            "action": "stop_production",
            "payload": {"material_id": "tijolos"},
            "reasoning_summary": "Machine breakdown forces halt",
        }]
    })

    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    decision = (await session.execute(
        text(
            "SELECT action FROM agent_decisions "
            "WHERE entity_id='factory-001' AND action='stop_production' "
            "ORDER BY created_at DESC LIMIT 1"
        )
    )).scalar_one_or_none()
    assert decision == "stop_production"


async def test_production_stopped_after_chaos(seeded_simulation_client):
    client, session, _ = seeded_simulation_client

    await session.execute(
        text(
            "UPDATE factory_products SET production_rate_current=2 "
            "WHERE factory_id='factory-001' AND material_id='tijolos'"
        )
    )
    await session.execute(
        text(
            "INSERT INTO factory_products (factory_id, material_id, stock, stock_reserved, stock_max, production_rate_max, production_rate_current) "
            "VALUES ('factory-001','cimento',50,0,100,10,7) "
            "ON CONFLICT (factory_id, material_id) DO UPDATE SET production_rate_current=7"
        )
    )
    await session.commit()

    await _inject_chaos(
        client,
        event_type="machine_breakdown",
        entity_type="factory",
        entity_id="factory-001",
        payload={"material_id": "tijolos", "severity": "high"},
        current_tick=0,
    )

    llm = make_entity_routing_llm(**{
        "factory-001": [{
            "action": "stop_production",
            "payload": {"material_id": "tijolos"},
            "reasoning_summary": "Halt tijolos",
        }]
    })

    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    tijolos_rate = await _get_production_rate(session, "factory-001", "tijolos")
    assert tijolos_rate == 0.0, f"tijolos production must be stopped, got {tijolos_rate}"

    cimento_rate = await _get_production_rate(session, "factory-001", "cimento")
    assert cimento_rate == 7.0, (
        f"cimento on same factory must be unaffected by tijolos breakdown, got {cimento_rate}"
    )

    vergalhao_rate_f002 = await _get_production_rate(session, "factory-002", "vergalhao")
    assert vergalhao_rate_f002 is not None
    cimento_rate_f003 = await _get_production_rate(session, "factory-003", "cimento")
    assert cimento_rate_f003 is not None, (
        "Other factories must be completely unaffected by factory-001 chaos"
    )


async def test_chaos_demand_spike_triggers_store(seeded_simulation_client):
    client, session, _ = seeded_simulation_client

    resp = await _inject_chaos(
        client,
        event_type="demand_spike",
        entity_type="store",
        entity_id="store-001",
        payload={"material_id": "cimento", "multiplier": 5.0},
        current_tick=0,
    )
    assert resp.status_code == 201

    llm = make_entity_routing_llm(**{
        "store-001": [{
            "action": "order_replenishment",
            "payload": {
                "material_id": "cimento",
                "quantity_tons": 60.0,
                "from_warehouse_id": "warehouse-002",
            },
            "reasoning_summary": "Demand spike",
        }]
    })

    with patch("src.agents.base.ChatOpenAI", return_value=llm):
        await advance_ticks_with_settle(client, 1)

    row = (await session.execute(
        text(
            "SELECT action, payload FROM agent_decisions "
            "WHERE entity_id='store-001' AND action='order_replenishment' "
            "ORDER BY created_at DESC LIMIT 1"
        )
    )).first()
    assert row is not None
    assert row.action == "order_replenishment"
    assert float(row.payload["quantity_tons"]) == 60.0
