import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.material import MaterialService
from src.services import ConflictError, NotFoundError


@pytest.fixture
def repo():
    return AsyncMock()


@pytest.fixture
def service(repo):
    return MaterialService(repo)


@pytest.mark.asyncio
async def test_list_materials_returns_all(service, repo):
    expected = [MagicMock(), MagicMock()]
    repo.get_all.return_value = expected
    result = await service.list_materials()
    repo.get_all.assert_called_once_with(active_only=False)
    assert result == expected


@pytest.mark.asyncio
async def test_list_materials_active_only_filters(service, repo):
    expected = [MagicMock()]
    repo.get_all.return_value = expected
    result = await service.list_materials(active_only=True)
    repo.get_all.assert_called_once_with(active_only=True)
    assert result == expected


@pytest.mark.asyncio
async def test_create_material_delegates_to_repo(service, repo):
    data = {"id": "tijolos", "name": "Tijolos"}
    expected = MagicMock()
    repo.create.return_value = expected
    result = await service.create_material(data)
    repo.create.assert_called_once_with(data)
    assert result == expected


@pytest.mark.asyncio
async def test_update_material_raises_not_found_when_repo_returns_none(service, repo):
    repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.update_material("nonexistent", {"name": "New Name"})


@pytest.mark.asyncio
async def test_update_material_returns_updated_material(service, repo):
    repo.get_by_id.return_value = MagicMock()
    updated = MagicMock()
    repo.update.return_value = updated
    result = await service.update_material("tijolos", {"name": "Tijolos Novos"})
    repo.update.assert_called_once_with("tijolos", {"name": "Tijolos Novos"})
    assert result == updated


@pytest.mark.asyncio
async def test_deactivate_material_raises_conflict_if_referenced_by_factory(service, repo):
    repo.has_linked_entities.return_value = True
    with pytest.raises(ConflictError):
        await service.deactivate_material("tijolos")


@pytest.mark.asyncio
async def test_deactivate_material_raises_conflict_if_referenced_by_warehouse(service, repo):
    repo.has_linked_entities.return_value = True
    with pytest.raises(ConflictError):
        await service.deactivate_material("cimento")


@pytest.mark.asyncio
async def test_deactivate_material_raises_conflict_if_referenced_by_store(service, repo):
    repo.has_linked_entities.return_value = True
    with pytest.raises(ConflictError):
        await service.deactivate_material("vergalhao")


@pytest.mark.asyncio
async def test_deactivate_material_sets_is_active_false_when_no_references(service, repo):
    repo.has_linked_entities.return_value = False
    deactivated = MagicMock()
    deactivated.is_active = False
    repo.update.return_value = deactivated
    result = await service.deactivate_material("tijolos")
    repo.has_linked_entities.assert_called_once_with("tijolos")
    repo.update.assert_called_once_with("tijolos", {"is_active": False})
    assert result.is_active is False
