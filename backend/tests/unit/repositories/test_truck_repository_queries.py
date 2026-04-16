from unittest.mock import AsyncMock, MagicMock

import pytest

from src.repositories.truck import TruckRepository


def _make_truck(id="truck_01", status="idle", truck_type="terceiro", factory_id=None):
    truck = MagicMock()
    truck.id = id
    truck.status = status
    truck.truck_type = truck_type
    truck.factory_id = factory_id
    return truck


@pytest.mark.asyncio
async def test_get_idle_by_factory_returns_idle_proprietario():
    truck = _make_truck(id="truck_prop", factory_id="factory_01")
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = truck
    session.execute.return_value = result

    repo = TruckRepository(session)
    found = await repo.get_idle_by_factory("factory_01")

    assert found is not None
    assert found.id == "truck_prop"


@pytest.mark.asyncio
async def test_get_idle_by_factory_returns_none_when_all_busy():
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    repo = TruckRepository(session)
    found = await repo.get_idle_by_factory("factory_01")

    assert found is None


@pytest.mark.asyncio
async def test_get_nearest_idle_third_party_returns_closest():
    truck = _make_truck(id="truck_close", truck_type="terceiro")
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = truck
    session.execute.return_value = result

    repo = TruckRepository(session)
    found = await repo.get_nearest_idle_third_party(-23.5, -46.6)

    assert found is not None
    assert found.id == "truck_close"


@pytest.mark.asyncio
async def test_get_all_in_maintenance_returns_only_maintenance():
    truck = _make_truck(id="truck_maint", status="maintenance")
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [truck]
    session.execute.return_value = result

    repo = TruckRepository(session)
    trucks = await repo.get_all_in_maintenance()

    assert len(trucks) == 1
    assert trucks[0].id == "truck_maint"
