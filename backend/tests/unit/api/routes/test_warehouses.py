import pytest
from unittest.mock import AsyncMock, MagicMock

import httpx
from httpx import ASGITransport

from src.main import app
from src.api.dependencies import get_warehouse_service
from src.services import NotFoundError


@pytest.fixture
def mock_service():
    return AsyncMock()


@pytest.fixture
async def client(mock_service):
    app.dependency_overrides[get_warehouse_service] = lambda: mock_service
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _make_warehouse(
    id: str = "wh-001",
    name: str = "Armazem Ribeirao Preto",
    lat: float = -21.17,
    lng: float = -47.81,
    region: str = "Ribeirao Preto",
    capacity_total: float = 500.0,
    status: str = "active",
):
    w = MagicMock()
    w.id = id
    w.name = name
    w.lat = lat
    w.lng = lng
    w.region = region
    w.capacity_total = capacity_total
    w.status = status
    w.stocks = []
    return w


@pytest.mark.asyncio
async def test_list_warehouses(client, mock_service):
    warehouses = [_make_warehouse("wh-001"), _make_warehouse("wh-002", "Armazem Jundiai")]
    mock_service.list_warehouses.return_value = warehouses

    resp = await client.get("/api/v1/entities/warehouses/")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    mock_service.list_warehouses.assert_called_once()


@pytest.mark.asyncio
async def test_get_warehouse(client, mock_service):
    warehouse = _make_warehouse("wh-001")
    mock_service.get_warehouse.return_value = warehouse

    resp = await client.get("/api/v1/entities/warehouses/wh-001")

    assert resp.status_code == 200
    mock_service.get_warehouse.assert_called_once_with("wh-001")


@pytest.mark.asyncio
async def test_get_warehouse_not_found(client, mock_service):
    mock_service.get_warehouse.side_effect = NotFoundError("Warehouse 'nonexistent' not found")

    resp = await client.get("/api/v1/entities/warehouses/nonexistent")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_warehouse(client, mock_service):
    created = _make_warehouse("wh-new", "Novo Armazem")
    mock_service.create_warehouse.return_value = created

    resp = await client.post(
        "/api/v1/entities/warehouses/",
        json={
            "name": "Novo Armazem",
            "lat": -23.5,
            "lng": -46.6,
            "region": "Sao Paulo",
            "capacity_total": 300.0,
        },
    )

    assert resp.status_code == 201
    mock_service.create_warehouse.assert_called_once()


@pytest.mark.asyncio
async def test_update_warehouse(client, mock_service):
    updated = _make_warehouse("wh-001", "Armazem Ribeirao Premium")
    mock_service.update_warehouse.return_value = updated

    resp = await client.patch(
        "/api/v1/entities/warehouses/wh-001",
        json={"name": "Armazem Ribeirao Premium"},
    )

    assert resp.status_code == 200
    mock_service.update_warehouse.assert_called_once_with("wh-001", {"name": "Armazem Ribeirao Premium"})


@pytest.mark.asyncio
async def test_update_warehouse_not_found(client, mock_service):
    mock_service.update_warehouse.side_effect = NotFoundError("Warehouse 'nonexistent' not found")

    resp = await client.patch(
        "/api/v1/entities/warehouses/nonexistent",
        json={"name": "Whatever"},
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_warehouse(client, mock_service):
    mock_service.delete_warehouse.return_value = None

    resp = await client.delete("/api/v1/entities/warehouses/wh-001")

    assert resp.status_code == 200
    mock_service.delete_warehouse.assert_called_once_with("wh-001")


@pytest.mark.asyncio
async def test_delete_warehouse_not_found(client, mock_service):
    mock_service.delete_warehouse.side_effect = NotFoundError("Warehouse 'nonexistent' not found")

    resp = await client.delete("/api/v1/entities/warehouses/nonexistent")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_adjust_warehouse_stock(client, mock_service):
    mock_service.adjust_stock.return_value = None

    resp = await client.patch(
        "/api/v1/entities/warehouses/wh-001/stock",
        json={"material_id": "mat-1", "delta": 10.0},
    )

    assert resp.status_code == 200
    mock_service.adjust_stock.assert_called_once_with("wh-001", "mat-1", 10.0)


@pytest.mark.asyncio
async def test_adjust_warehouse_stock_not_found(client, mock_service):
    mock_service.adjust_stock.side_effect = NotFoundError("Warehouse 'nonexistent' not found")

    resp = await client.patch(
        "/api/v1/entities/warehouses/nonexistent/stock",
        json={"material_id": "mat-1", "delta": 5.0},
    )

    assert resp.status_code == 404
