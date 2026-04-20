import json

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import advance_n_ticks

pytestmark = pytest.mark.asyncio


async def test_stock_depletes_over_ticks(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    initial = await async_session.execute(
        text(
            "SELECT stock, demand_rate FROM store_stocks "
            "WHERE store_id='store-001' AND material_id='cimento'"
        )
    )
    row = initial.one()
    initial_stock, demand_rate = float(row.stock), float(row.demand_rate)
    ticks_to_zero = int(initial_stock / demand_rate) if demand_rate > 0 else 99
    assert ticks_to_zero >= 1, "Seed data must allow at least 1 tick of depletion"

    await advance_n_ticks(client, ticks_to_zero)

    await async_session.rollback()
    result = await async_session.execute(
        text("SELECT stock FROM store_stocks WHERE store_id='store-001' AND material_id='cimento'")
    )
    stock = result.scalar_one()
    assert stock == pytest.approx(0.0, abs=0.01), (
        f"Stock must reach 0 after {ticks_to_zero} ticks "
        f"(initial={initial_stock}, demand_rate={demand_rate})"
    )


async def test_stock_depletes_progressively(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    await advance_n_ticks(client, 1)

    await async_session.rollback()
    result = await async_session.execute(
        text("SELECT stock FROM store_stocks WHERE store_id='store-001' AND material_id='cimento'")
    )
    stock_after_tick_1 = result.scalar_one()
    assert stock_after_tick_1 == pytest.approx(15.0)

    await advance_n_ticks(client, 1)

    await async_session.rollback()
    result = await async_session.execute(
        text("SELECT stock FROM store_stocks WHERE store_id='store-001' AND material_id='cimento'")
    )
    stock_after_tick_2 = result.scalar_one()
    assert stock_after_tick_2 == pytest.approx(7.5)

    assert stock_after_tick_2 < stock_after_tick_1


async def test_world_state_published_each_tick(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    await advance_n_ticks(client, 3)

    world_state_payloads = []
    for call in mock_redis.publish.call_args_list:
        if "world_state" in call.args[0]:
            raw = call.args[1] if isinstance(call.args[1], str) else call.args[1].decode()
            world_state_payloads.append(json.loads(raw))

    assert len(world_state_payloads) >= 3, (
        f"Expected >=3 world_state publishes, got {len(world_state_payloads)}"
    )
    for payload in world_state_payloads:
        assert "tick" in payload, "Published world_state must contain 'tick'"
        assert "factories" in payload, "Published world_state must contain 'factories'"
        assert "stores" in payload, "Published world_state must contain 'stores'"
        assert "trucks" in payload, "Published world_state must contain 'trucks'"


async def test_tick_counter_advances(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    await advance_n_ticks(client, 5)

    resp = await client.get("/simulation/status")
    assert resp.status_code == 200
    assert resp.json()["current_tick"] == 5
