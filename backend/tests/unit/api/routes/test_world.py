from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport

from src.main import app
from src.api.dependencies import get_world_state_service, get_simulation_service


@pytest.fixture
def mock_world_state_service():
    service = AsyncMock()
    service.load = AsyncMock()
    return service


@pytest.fixture
def mock_simulation_service():
    service = AsyncMock()
    service.get_status = MagicMock()
    return service


@pytest.fixture
async def client(mock_world_state_service, mock_simulation_service):
    app.dependency_overrides[get_world_state_service] = lambda: mock_world_state_service
    app.dependency_overrides[get_simulation_service] = lambda: mock_simulation_service
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_snapshot(client, mock_world_state_service):
    mock_world_state_service.load.return_value = {
        "tick": 1,
        "simulated_timestamp": "2025-01-01T01:00:00",
        "materials": [{"id": "tijolos", "name": "Tijolos", "is_active": True}],
        "factories": [],
        "warehouses": [],
        "stores": [],
        "trucks": [],
    }

    response = await client.get("/api/v1/world/snapshot")

    assert response.status_code == 200
    data = response.json()
    assert data["tick"] == 1
    assert len(data["materials"]) == 1
    assert data["materials"][0]["id"] == "tijolos"
    mock_world_state_service.load.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_snapshot_returns_complete_payload(client, mock_world_state_service):
    mock_world_state_service.load.return_value = {
        "tick": 10,
        "simulated_timestamp": "2025-01-01T10:00:00",
        "materials": [],
        "factories": [{"id": "f1", "name": "Factory Alpha"}],
        "warehouses": [{"id": "w1", "name": "Warehouse Central"}],
        "stores": [{"id": "s1", "name": "Store Downtown"}],
        "trucks": [{"id": "t1", "plate": "ABC-1234"}],
    }

    response = await client.get("/api/v1/world/snapshot")

    assert response.status_code == 200
    data = response.json()
    assert data["tick"] == 10
    assert len(data["factories"]) == 1
    assert len(data["warehouses"]) == 1
    assert len(data["stores"]) == 1
    assert len(data["trucks"]) == 1


@pytest.mark.asyncio
async def test_get_tick(client, mock_simulation_service):
    mock_simulation_service.get_status.return_value = {
        "running": False,
        "current_tick": 42,
        "tick_interval_seconds": 10,
    }

    response = await client.get("/api/v1/world/tick")

    assert response.status_code == 200
    data = response.json()
    assert data["current_tick"] == 42
