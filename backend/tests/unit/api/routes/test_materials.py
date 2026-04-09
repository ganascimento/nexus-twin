import pytest
from unittest.mock import AsyncMock, MagicMock

import httpx
from httpx import ASGITransport

from src.main import app
from src.api.dependencies import get_material_service
from src.services import NotFoundError, ConflictError


@pytest.fixture
def mock_service():
    return AsyncMock()


@pytest.fixture
async def client(mock_service):
    app.dependency_overrides[get_material_service] = lambda: mock_service
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _make_material(id: str = "tijolos", name: str = "Tijolos", is_active: bool = True):
    m = MagicMock()
    m.id = id
    m.name = name
    m.is_active = is_active
    return m


@pytest.mark.asyncio
async def test_list_materials(client, mock_service):
    materials = [_make_material("tijolos", "Tijolos"), _make_material("cimento", "Cimento")]
    mock_service.list_materials.return_value = materials

    resp = await client.get("/api/v1/materials/")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    mock_service.list_materials.assert_called_once_with(active_only=False)


@pytest.mark.asyncio
async def test_list_materials_active_only(client, mock_service):
    mock_service.list_materials.return_value = [_make_material()]

    resp = await client.get("/api/v1/materials/", params={"active_only": "true"})

    assert resp.status_code == 200
    mock_service.list_materials.assert_called_once_with(active_only=True)


@pytest.mark.asyncio
async def test_create_material(client, mock_service):
    created = _make_material("vergalhao", "Vergalhao")
    mock_service.create_material.return_value = created

    resp = await client.post("/api/v1/materials/", json={"name": "Vergalhao"})

    assert resp.status_code == 201
    mock_service.create_material.assert_called_once()


@pytest.mark.asyncio
async def test_update_material(client, mock_service):
    updated = _make_material("tijolos", "Tijolos Premium")
    mock_service.update_material.return_value = updated

    resp = await client.patch("/api/v1/materials/tijolos", json={"name": "Tijolos Premium"})

    assert resp.status_code == 200
    mock_service.update_material.assert_called_once_with("tijolos", {"name": "Tijolos Premium"})


@pytest.mark.asyncio
async def test_update_material_not_found(client, mock_service):
    mock_service.update_material.side_effect = NotFoundError("Material 'nonexistent' not found")

    resp = await client.patch("/api/v1/materials/nonexistent", json={"name": "Whatever"})

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_deactivate_material(client, mock_service):
    deactivated = _make_material("tijolos", "Tijolos", is_active=False)
    mock_service.deactivate_material.return_value = deactivated

    resp = await client.patch("/api/v1/materials/tijolos/deactivate")

    assert resp.status_code == 200
    mock_service.deactivate_material.assert_called_once_with("tijolos")


@pytest.mark.asyncio
async def test_deactivate_material_with_linked_entities_returns_409(client, mock_service):
    mock_service.deactivate_material.side_effect = ConflictError(
        "Material 'tijolos' is still referenced by active entities"
    )

    resp = await client.patch("/api/v1/materials/tijolos/deactivate")

    assert resp.status_code == 409
