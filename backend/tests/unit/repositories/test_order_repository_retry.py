from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.repositories.order import OrderRepository


def _make_order(status="rejected", retry_after_tick=6, age_ticks=8):
    order = MagicMock()
    order.id = uuid4()
    order.status = status
    order.retry_after_tick = retry_after_tick
    order.age_ticks = age_ticks
    return order


@pytest.mark.asyncio
async def test_get_retry_eligible_returns_expired_backoff():
    order = _make_order(status="rejected", retry_after_tick=6, age_ticks=8)
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [order]
    session.execute.return_value = result

    repo = OrderRepository(session)
    orders = await repo.get_retry_eligible("store_01")

    assert len(orders) == 1
    assert orders[0].status == "rejected"


@pytest.mark.asyncio
async def test_get_retry_eligible_excludes_active_backoff():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result

    repo = OrderRepository(session)
    orders = await repo.get_retry_eligible("store_01")

    assert orders == []


@pytest.mark.asyncio
async def test_get_retry_eligible_excludes_non_rejected():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result

    repo = OrderRepository(session)
    orders = await repo.get_retry_eligible("store_01")

    assert orders == []
