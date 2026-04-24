import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.repositories.order import OrderRepository


@pytest.mark.asyncio
async def test_mark_in_transit_bulk_flips_all_ids():
    session = AsyncMock()
    result = MagicMock()
    session.execute.return_value = result

    repo = OrderRepository(session)
    ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    await repo.mark_in_transit_bulk(ids)

    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_mark_in_transit_bulk_noop_on_empty_list():
    session = AsyncMock()
    repo = OrderRepository(session)

    await repo.mark_in_transit_bulk([])

    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_rollback_in_transit_bulk_flips_back_to_confirmed():
    session = AsyncMock()
    result = MagicMock()
    session.execute.return_value = result

    repo = OrderRepository(session)
    ids = [uuid.uuid4(), uuid.uuid4()]
    await repo.rollback_in_transit_bulk(ids)

    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_rollback_in_transit_bulk_noop_on_empty_list():
    session = AsyncMock()
    repo = OrderRepository(session)

    await repo.rollback_in_transit_bulk([])

    session.execute.assert_not_called()
