import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import advance_n_ticks

pytestmark = pytest.mark.asyncio


async def test_stock_depletes_over_ticks(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    await advance_n_ticks(client, 3)

    await async_session.rollback()
    result = await async_session.execute(
        text("SELECT stock FROM store_stocks WHERE store_id='store-001' AND material_id='cimento'")
    )
    stock = result.scalar_one()
    assert stock == pytest.approx(0.0, abs=0.01)


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

    world_state_publish_count = sum(
        1 for call in mock_redis.publish.call_args_list
        if "world_state" in call.args[0]
    )
    assert world_state_publish_count >= 3


async def test_tick_counter_advances(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    await advance_n_ticks(client, 5)

    resp = await client.get("/simulation/status")
    assert resp.status_code == 200
    assert resp.json()["current_tick"] == 5
