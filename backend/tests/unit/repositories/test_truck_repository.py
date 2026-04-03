from unittest.mock import AsyncMock, MagicMock

import pytest
from src.database.models import Truck
from src.repositories.truck import TruckRepository


@pytest.mark.asyncio
async def test_get_by_factory_filters_by_factory_id():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        Truck(id="t1", factory_id="f1"),
        Truck(id="t2", factory_id="f1"),
    ]
    session.execute.return_value = result

    repo = TruckRepository(session)
    trucks = await repo.get_by_factory("f1")

    assert len(trucks) == 2
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_try_lock_for_evaluation_returns_true_when_idle():
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 1
    session.execute.return_value = result

    repo = TruckRepository(session)
    locked = await repo.try_lock_for_evaluation("t1")

    assert locked is True


@pytest.mark.asyncio
async def test_try_lock_for_evaluation_returns_false_when_not_idle():
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    repo = TruckRepository(session)
    locked = await repo.try_lock_for_evaluation("t1")

    assert locked is False


@pytest.mark.asyncio
async def test_set_cargo_accepts_none():
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 1
    session.execute.return_value = result

    repo = TruckRepository(session)
    await repo.set_cargo("t1", None)

    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_update_degradation_updates_both_fields():
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 1
    session.execute.return_value = result

    repo = TruckRepository(session)
    await repo.update_degradation(id="t1", degradation=0.45, breakdown_risk=0.05)

    session.execute.assert_called_once()
