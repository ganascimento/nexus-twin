from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport

from src.main import app
from src.api.dependencies import get_simulation_service
from src.services import ConflictError


@pytest.fixture
def mock_simulation_service():
    service = AsyncMock()
    service.start = AsyncMock()
    service.stop = AsyncMock()
    service.advance_tick = AsyncMock()
    service.set_tick_interval = MagicMock()
    service.get_status = MagicMock()
    return service


@pytest.fixture
async def client(mock_simulation_service):
    app.dependency_overrides[get_simulation_service] = lambda: mock_simulation_service
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_start_simulation(client, mock_simulation_service):
    response = await client.post("/api/v1/simulation/start")
    assert response.status_code == 200
    mock_simulation_service.start.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_simulation(client, mock_simulation_service):
    response = await client.post("/api/v1/simulation/stop")
    assert response.status_code == 200
    mock_simulation_service.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_advance_tick_when_stopped(client, mock_simulation_service):
    mock_simulation_service.advance_tick.return_value = {
        "tick": 2,
        "simulated_timestamp": "2025-01-01T02:00:00",
        "factories": [],
        "warehouses": [],
        "stores": [],
        "trucks": [],
        "materials": [],
    }

    response = await client.post("/api/v1/simulation/tick")

    assert response.status_code == 200
    data = response.json()
    assert data["tick"] == 2
    mock_simulation_service.advance_tick.assert_awaited_once()


@pytest.mark.asyncio
async def test_advance_tick_when_running_returns_409(client, mock_simulation_service):
    mock_simulation_service.advance_tick.side_effect = ConflictError(
        "Cannot advance tick while simulation is running"
    )

    response = await client.post("/api/v1/simulation/tick")

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_status(client, mock_simulation_service):
    mock_simulation_service.get_status.return_value = {
        "running": True,
        "current_tick": 42,
        "tick_interval": 10,
        "simulated_timestamp": "2025-01-02T18:00:00",
    }

    response = await client.get("/api/v1/simulation/status")

    assert response.status_code == 200
    data = response.json()
    assert data["running"] is True
    assert data["current_tick"] == 42
    assert data["tick_interval"] == 10
    assert data["simulated_timestamp"] == "2025-01-02T18:00:00"
    mock_simulation_service.get_status.assert_called_once()


@pytest.mark.asyncio
async def test_set_speed_valid(client, mock_simulation_service):
    response = await client.patch(
        "/api/v1/simulation/speed", json={"tick_interval_seconds": 15}
    )

    assert response.status_code == 200
    mock_simulation_service.set_tick_interval.assert_called_once_with(15)


@pytest.mark.asyncio
async def test_set_speed_below_minimum_returns_400(client, mock_simulation_service):
    mock_simulation_service.set_tick_interval.side_effect = ValueError(
        "Tick interval must be at least 10 seconds"
    )

    response = await client.patch(
        "/api/v1/simulation/speed", json={"tick_interval_seconds": 5}
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_set_speed_at_minimum_boundary(client, mock_simulation_service):
    response = await client.patch(
        "/api/v1/simulation/speed", json={"tick_interval_seconds": 10}
    )

    assert response.status_code == 200
    mock_simulation_service.set_tick_interval.assert_called_once_with(10)
