from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.repositories.order import OrderRepository


def _make_order(id=None, status="confirmed", age_ticks=5):
    order = MagicMock()
    order.id = id or uuid4()
    order.status = status
    order.age_ticks = age_ticks
    return order


@pytest.mark.asyncio
async def test_get_confirmed_without_route_returns_orphaned():
    order = _make_order(status="confirmed")
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [order]
    session.execute.return_value = result

    repo = OrderRepository(session)
    orders = await repo.get_confirmed_without_route(limit=10)

    assert len(orders) == 1
    assert orders[0].status == "confirmed"


@pytest.mark.asyncio
async def test_get_confirmed_without_route_excludes_with_active_route():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result

    repo = OrderRepository(session)
    orders = await repo.get_confirmed_without_route(limit=10)

    assert orders == []


@pytest.mark.asyncio
async def test_get_confirmed_without_route_orders_by_age_desc():
    old_order = _make_order(age_ticks=10)
    new_order = _make_order(age_ticks=2)
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [old_order, new_order]
    session.execute.return_value = result

    repo = OrderRepository(session)
    orders = await repo.get_confirmed_without_route(limit=10)

    assert len(orders) == 2
    assert orders[0].age_ticks >= orders[1].age_ticks
