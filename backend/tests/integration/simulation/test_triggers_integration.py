import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


async def test_tick_completes_with_seeded_data(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    response = await client.post("/simulation/tick")
    assert response.status_code == 200
    assert response.json()["tick"] == 1


async def test_store_stock_below_threshold_triggers_agent(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    await async_session.execute(
        text(
            "UPDATE store_stocks SET stock=2 "
            "WHERE store_id='store-001' AND material_id='cimento'"
        )
    )
    await async_session.commit()

    response = await client.post("/simulation/tick")
    assert response.status_code == 200


async def test_comfortable_stock_no_crash(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    response = await client.post("/simulation/tick")
    assert response.status_code == 200
    assert response.json()["status"] == "advanced"


async def test_multiple_ticks_sequential(seeded_simulation_client):
    client, async_session, mock_redis = seeded_simulation_client

    for i in range(1, 4):
        response = await client.post("/simulation/tick")
        assert response.status_code == 200
        assert response.json()["tick"] == i

    status_response = await client.get("/simulation/status")
    assert status_response.status_code == 200
    assert status_response.json()["current_tick"] == 3
