import pytest
from unittest.mock import AsyncMock, MagicMock

import httpx
from httpx import ASGITransport

from src.main import app
from src.api.dependencies import get_factory_service
from src.services import NotFoundError


@pytest.fixture
def mock_service():
    return AsyncMock()


@pytest.fixture
async def client(mock_service):
    app.dependency_overrides[get_factory_service] = lambda: mock_service
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _make_factory(
    id: str = "factory-001",
    name: str = "Fabrica Campinas",
    lat: float = -22.9,
    lng: float = -47.06,
    status: str = "active",
):
    f = MagicMock()
    f.id = id
    f.name = name
    f.lat = lat
    f.lng = lng
    f.status = status
    f.products = []
    f.partner_warehouses = []
    return f


@pytest.mark.asyncio
async def test_list_factories(client, mock_service):
    factories = [_make_factory("factory-001"), _make_factory("factory-002", "Fabrica Sorocaba")]
    mock_service.list_factories.return_value = factories

    resp = await client.get("/api/v1/entities/factories/")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    mock_service.list_factories.assert_called_once()


@pytest.mark.asyncio
async def test_get_factory(client, mock_service):
    factory = _make_factory("factory-001")
    mock_service.get_factory.return_value = factory

    resp = await client.get("/api/v1/entities/factories/factory-001")

    assert resp.status_code == 200
    mock_service.get_factory.assert_called_once_with("factory-001")


@pytest.mark.asyncio
async def test_get_factory_not_found(client, mock_service):
    mock_service.get_factory.side_effect = NotFoundError("Factory 'nonexistent' not found")

    resp = await client.get("/api/v1/entities/factories/nonexistent")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_factory(client, mock_service):
    created = _make_factory("factory-new", "Nova Fabrica")
    mock_service.create_factory.return_value = created

    resp = await client.post(
        "/api/v1/entities/factories/",
        json={"name": "Nova Fabrica", "lat": -23.0, "lng": -47.0},
    )

    assert resp.status_code == 201
    mock_service.create_factory.assert_called_once()


@pytest.mark.asyncio
async def test_update_factory(client, mock_service):
    updated = _make_factory("factory-001", "Fabrica Campinas Atualizada")
    mock_service.update_factory.return_value = updated

    resp = await client.patch(
        "/api/v1/entities/factories/factory-001",
        json={"name": "Fabrica Campinas Atualizada"},
    )

    assert resp.status_code == 200
    mock_service.update_factory.assert_called_once_with("factory-001", {"name": "Fabrica Campinas Atualizada"})


@pytest.mark.asyncio
async def test_update_factory_not_found(client, mock_service):
    mock_service.update_factory.side_effect = NotFoundError("Factory 'nonexistent' not found")

    resp = await client.patch(
        "/api/v1/entities/factories/nonexistent",
        json={"name": "Whatever"},
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_factory(client, mock_service):
    mock_service.delete_factory.return_value = None

    resp = await client.delete("/api/v1/entities/factories/factory-001")

    assert resp.status_code == 200
    mock_service.delete_factory.assert_called_once_with("factory-001")


@pytest.mark.asyncio
async def test_delete_factory_not_found(client, mock_service):
    mock_service.delete_factory.side_effect = NotFoundError("Factory 'nonexistent' not found")

    resp = await client.delete("/api/v1/entities/factories/nonexistent")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_adjust_factory_stock(client, mock_service):
    mock_service.adjust_stock.return_value = None

    resp = await client.patch(
        "/api/v1/entities/factories/factory-001/stock",
        json={"material_id": "mat-1", "delta": 10.0},
    )

    assert resp.status_code == 200
    mock_service.adjust_stock.assert_called_once_with("factory-001", "mat-1", 10.0)


@pytest.mark.asyncio
async def test_adjust_factory_stock_not_found(client, mock_service):
    mock_service.adjust_stock.side_effect = NotFoundError("Factory 'nonexistent' not found")

    resp = await client.patch(
        "/api/v1/entities/factories/nonexistent/stock",
        json={"material_id": "mat-1", "delta": 5.0},
    )

    assert resp.status_code == 404
