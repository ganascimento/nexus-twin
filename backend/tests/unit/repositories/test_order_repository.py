import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.database.models import PendingOrder
from src.repositories.order import OrderRepository


def _make_order(order_id=None, requester_id="s1", active_route_id=None):
    order = PendingOrder(
        id=order_id or uuid.uuid4(),
        requester_type="store",
        requester_id=requester_id,
        target_type="warehouse",
        target_id="w1",
        material_id="m1",
        quantity_tons=10.0,
        status="pending",
        age_ticks=0,
    )
    object.__setattr__(order, "active_route_id", active_route_id)
    return order


@pytest.mark.asyncio
async def test_get_pending_for_target_only_returns_pending_confirmed():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _make_order(requester_id="s1"),
        _make_order(requester_id="s2"),
    ]
    session.execute.return_value = result

    repo = OrderRepository(session)
    orders = await repo.get_pending_for_target(target_id="w1")

    assert len(orders) == 2
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_increment_all_age_ticks_bulk_update():
    session = AsyncMock()
    result = MagicMock()
    session.execute.return_value = result

    repo = OrderRepository(session)
    await repo.increment_all_age_ticks()

    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_bulk_cancel_by_target_skips_active_routes():
    order_without_route = _make_order(requester_id="s1", active_route_id=None)
    order_with_route = _make_order(requester_id="s2", active_route_id=uuid.uuid4())

    select_result = MagicMock()
    select_result.scalars.return_value.all.return_value = [
        order_without_route,
        order_with_route,
    ]

    update_result = MagicMock()

    session = AsyncMock()
    session.execute.side_effect = [select_result, update_result]

    repo = OrderRepository(session)
    cancelled_requester_ids = await repo.bulk_cancel_by_target(
        target_id="w1",
        reason="warehouse_removed",
        skip_active_routes=True,
    )

    assert len(cancelled_requester_ids) == 1
    assert cancelled_requester_ids[0] == "s1"


@pytest.mark.asyncio
async def test_bulk_cancel_by_target_without_skip():
    order_a = _make_order(requester_id="s1", active_route_id=None)
    order_b = _make_order(requester_id="s2", active_route_id=uuid.uuid4())

    select_result = MagicMock()
    select_result.scalars.return_value.all.return_value = [order_a, order_b]

    update_result = MagicMock()

    session = AsyncMock()
    session.execute.side_effect = [select_result, update_result]

    repo = OrderRepository(session)
    cancelled_requester_ids = await repo.bulk_cancel_by_target(
        target_id="w1",
        reason="warehouse_removed",
        skip_active_routes=False,
    )

    assert len(cancelled_requester_ids) == 2


@pytest.mark.asyncio
async def test_bulk_cancel_by_requester_cancels_all_from_requester():
    session = AsyncMock()
    result = MagicMock()
    session.execute.return_value = result

    repo = OrderRepository(session)
    await repo.bulk_cancel_by_requester(
        requester_id="s1",
        reason="store_removed",
    )

    session.execute.assert_called_once()
