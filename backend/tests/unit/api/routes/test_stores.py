import pytest
from unittest.mock import AsyncMock, MagicMock

import httpx
from httpx import ASGITransport

from src.main import app
from src.api.dependencies import get_store_service
from src.services import NotFoundError


@pytest.fixture
def mock_service():
    return AsyncMock()


@pytest.fixture
async def client(mock_service):
    app.dependency_overrides[get_store_service] = lambda: mock_service
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _make_store(
    id: str = "store-1",
    name: str = "Loja Centro SP",
    lat: float = -23.55,
    lng: float = -46.63,
    status: str = "open",
    region: str = "SP Capital",
):
    s = MagicMock()
    s.id = id
    s.name = name
    s.lat = lat
    s.lng = lng
    s.status = status
    s.region = region
    return s


@pytest.mark.asyncio
async def test_list_stores(client, mock_service):
    stores = [_make_store("store-1", "Loja Centro SP"), _make_store("store-2", "Loja Zona Sul")]
    mock_service.list_stores.return_value = stores

    resp = await client.get("/api/v1/entities/stores/")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    mock_service.list_stores.assert_called_once()


@pytest.mark.asyncio
async def test_get_store(client, mock_service):
    store = _make_store("store-1", "Loja Centro SP")
    mock_service.get_store.return_value = store

    resp = await client.get("/api/v1/entities/stores/store-1")

    assert resp.status_code == 200
    mock_service.get_store.assert_called_once_with("store-1")


@pytest.mark.asyncio
async def test_get_store_not_found(client, mock_service):
    mock_service.get_store.side_effect = NotFoundError("Store 'nonexistent' not found")

    resp = await client.get("/api/v1/entities/stores/nonexistent")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_store(client, mock_service):
    created = _make_store("store-new", "Loja Nova")
    mock_service.create_store.return_value = created

    resp = await client.post(
        "/api/v1/entities/stores/",
        json={
            "name": "Loja Nova",
            "lat": -23.55,
            "lng": -46.63,
            "region": "SP Capital",
        },
    )

    assert resp.status_code == 201
    mock_service.create_store.assert_called_once()


@pytest.mark.asyncio
async def test_update_store(client, mock_service):
    updated = _make_store("store-1", "Loja Atualizada")
    mock_service.update_store.return_value = updated

    resp = await client.patch(
        "/api/v1/entities/stores/store-1",
        json={"name": "Loja Atualizada"},
    )

    assert resp.status_code == 200
    mock_service.update_store.assert_called_once_with("store-1", {"name": "Loja Atualizada"})


@pytest.mark.asyncio
async def test_update_store_not_found(client, mock_service):
    mock_service.update_store.side_effect = NotFoundError("Store 'nonexistent' not found")

    resp = await client.patch(
        "/api/v1/entities/stores/nonexistent",
        json={"name": "Whatever"},
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_store(client, mock_service):
    mock_service.delete_store.return_value = None

    resp = await client.delete("/api/v1/entities/stores/store-1")

    assert resp.status_code == 200
    mock_service.delete_store.assert_called_once_with("store-1")


@pytest.mark.asyncio
async def test_delete_store_not_found(client, mock_service):
    mock_service.delete_store.side_effect = NotFoundError("Store 'nonexistent' not found")

    resp = await client.delete("/api/v1/entities/stores/nonexistent")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_adjust_store_stock(client, mock_service):
    mock_service.adjust_stock.return_value = None

    resp = await client.patch(
        "/api/v1/entities/stores/store-1/stock",
        json={"material_id": "mat-1", "delta": 5.0},
    )

    assert resp.status_code == 200
    mock_service.adjust_stock.assert_called_once_with("store-1", "mat-1", 5.0)


@pytest.mark.asyncio
async def test_adjust_store_stock_not_found(client, mock_service):
    mock_service.adjust_stock.side_effect = NotFoundError("Store 'store-1' not found")

    resp = await client.patch(
        "/api/v1/entities/stores/store-1/stock",
        json={"material_id": "mat-1", "delta": 5.0},
    )

    assert resp.status_code == 404
