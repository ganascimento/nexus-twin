import pytest
from unittest.mock import AsyncMock, MagicMock

import httpx
from httpx import ASGITransport

from src.main import app
from src.api.dependencies import get_truck_service
from src.services import NotFoundError


@pytest.fixture
def mock_service():
    return AsyncMock()


@pytest.fixture
async def client(mock_service):
    app.dependency_overrides[get_truck_service] = lambda: mock_service
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _make_truck(
    id: str = "truck-1",
    name: str = "Caminhao Alpha",
    truck_type: str = "proprietario",
    status: str = "idle",
    degradation: float = 0.0,
    lat: float = -23.55,
    lng: float = -46.63,
):
    t = MagicMock()
    t.id = id
    t.name = name
    t.truck_type = truck_type
    t.status = status
    t.degradation = degradation
    t.lat = lat
    t.lng = lng
    return t


@pytest.mark.asyncio
async def test_list_trucks(client, mock_service):
    trucks = [
        _make_truck("truck-1", "Caminhao Alpha"),
        _make_truck("truck-2", "Caminhao Beta", truck_type="terceiro"),
    ]
    mock_service.list_trucks.return_value = trucks

    resp = await client.get("/api/v1/entities/trucks/")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    mock_service.list_trucks.assert_called_once()


@pytest.mark.asyncio
async def test_get_truck(client, mock_service):
    truck = _make_truck("truck-1", "Caminhao Alpha")
    mock_service.get_truck.return_value = truck

    resp = await client.get("/api/v1/entities/trucks/truck-1")

    assert resp.status_code == 200
    mock_service.get_truck.assert_called_once_with("truck-1")


@pytest.mark.asyncio
async def test_get_truck_not_found(client, mock_service):
    mock_service.get_truck.side_effect = NotFoundError("Truck 'nonexistent' not found")

    resp = await client.get("/api/v1/entities/trucks/nonexistent")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_truck(client, mock_service):
    created = _make_truck("truck-new", "Caminhao Novo")
    mock_service.create_truck.return_value = created

    resp = await client.post(
        "/api/v1/entities/trucks/",
        json={
            "name": "Caminhao Novo",
            "truck_type": "proprietario",
            "lat": -23.55,
            "lng": -46.63,
        },
    )

    assert resp.status_code == 201
    mock_service.create_truck.assert_called_once()


@pytest.mark.asyncio
async def test_delete_truck(client, mock_service):
    mock_service.delete_truck.return_value = None

    resp = await client.delete("/api/v1/entities/trucks/truck-1")

    assert resp.status_code == 200
    mock_service.delete_truck.assert_called_once_with("truck-1")


@pytest.mark.asyncio
async def test_delete_truck_not_found(client, mock_service):
    mock_service.delete_truck.side_effect = NotFoundError("Truck 'nonexistent' not found")

    resp = await client.delete("/api/v1/entities/trucks/nonexistent")

    assert resp.status_code == 404
