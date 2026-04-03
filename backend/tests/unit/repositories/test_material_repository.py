from unittest.mock import AsyncMock, MagicMock

import pytest
from src.database.models import Material
from src.repositories.material import MaterialRepository


@pytest.mark.asyncio
async def test_get_all_returns_all_materials():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        Material(id="m1", name="tijolos", is_active=True),
        Material(id="m2", name="cimento", is_active=False),
    ]
    session.execute.return_value = result

    repo = MaterialRepository(session)
    materials = await repo.get_all()

    assert len(materials) == 2
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_all_active_only_filters():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        Material(id="m1", name="tijolos", is_active=True),
    ]
    session.execute.return_value = result

    repo = MaterialRepository(session)
    materials = await repo.get_all(active_only=True)

    assert len(materials) == 1
    assert materials[0].is_active is True
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_not_found():
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    repo = MaterialRepository(session)
    material = await repo.get_by_id("nonexistent")

    assert material is None


@pytest.mark.asyncio
async def test_create_inserts_and_returns():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    repo = MaterialRepository(session)
    material = await repo.create({"id": "m1", "name": "tijolos"})

    session.add.assert_called_once()
    session.flush.assert_called_once()
    assert material is not None


@pytest.mark.asyncio
async def test_has_linked_entities_returns_true():
    session = AsyncMock()
    result = MagicMock()
    result.scalar.return_value = 1
    session.execute.return_value = result

    repo = MaterialRepository(session)
    has_links = await repo.has_linked_entities("m1")

    assert has_links is True


@pytest.mark.asyncio
async def test_has_linked_entities_returns_false():
    session = AsyncMock()
    result = MagicMock()
    result.scalar.return_value = 0
    session.execute.return_value = result

    repo = MaterialRepository(session)
    has_links = await repo.has_linked_entities("m1")

    assert has_links is False
