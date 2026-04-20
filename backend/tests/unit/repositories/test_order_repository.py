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
    order_without_route = _make_order(requester_id="s1")
    order_with_route = _make_order(requester_id="s2")

    select_orders_result = MagicMock()
    select_orders_result.scalars.return_value.all.return_value = [
        order_without_route,
        order_with_route,
    ]

    select_active_routes_result = MagicMock()
    select_active_routes_result.scalars.return_value.all.return_value = [
        order_with_route.id,
    ]

    update_result = MagicMock()

    session = AsyncMock()
    session.execute.side_effect = [
        select_orders_result,
        select_active_routes_result,
        update_result,
    ]

    repo = OrderRepository(session)
    cancelled = await repo.bulk_cancel_by_target(
        target_id="w1",
        reason="warehouse_removed",
        skip_active_routes=True,
    )

    assert len(cancelled) == 1
    assert cancelled[0].requester_id == "s1"


@pytest.mark.asyncio
async def test_bulk_cancel_by_target_without_skip():
    order_a = _make_order(requester_id="s1")
    order_b = _make_order(requester_id="s2")

    select_result = MagicMock()
    select_result.scalars.return_value.all.return_value = [order_a, order_b]

    update_result = MagicMock()

    session = AsyncMock()
    session.execute.side_effect = [select_result, update_result]

    repo = OrderRepository(session)
    cancelled = await repo.bulk_cancel_by_target(
        target_id="w1",
        reason="warehouse_removed",
        skip_active_routes=False,
    )

    assert len(cancelled) == 2


@pytest.mark.asyncio
async def test_bulk_cancel_by_requester_cancels_all_from_requester():
    order_a = _make_order(requester_id="s1")
    select_result = MagicMock()
    select_result.scalars.return_value.all.return_value = [order_a]
    update_result = MagicMock()

    session = AsyncMock()
    session.execute.side_effect = [select_result, update_result]

    repo = OrderRepository(session)
    cancelled = await repo.bulk_cancel_by_requester(
        requester_id="s1",
        reason="store_removed",
    )

    assert len(cancelled) == 1
    assert cancelled[0].requester_id == "s1"
    assert session.execute.call_count == 2


# ---------------------------------------------------------------------------
# Feature 25 — order-based trigger methods
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_untriggered_for_target_returns_pending_only():
    pending_order = _make_order(requester_id="s1")
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [pending_order]
    session.execute.return_value = result

    repo = OrderRepository(session)
    orders = await repo.get_untriggered_for_target("w1")

    assert len(orders) == 1
    assert orders[0].status == "pending"
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_untriggered_for_target_excludes_triggered():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result

    repo = OrderRepository(session)
    orders = await repo.get_untriggered_for_target("w1")

    assert orders == []


@pytest.mark.asyncio
async def test_mark_triggered_sets_tick():
    order_id = uuid.uuid4()
    session = AsyncMock()
    session.execute.return_value = MagicMock()

    repo = OrderRepository(session)
    await repo.mark_triggered(order_id, 10)

    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_triggered_but_pending_for_target():
    order = _make_order(requester_id="s1")
    object.__setattr__(order, "triggered_at_tick", 5)
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [order]
    session.execute.return_value = result

    repo = OrderRepository(session)
    orders = await repo.get_triggered_but_pending_for_target("factory_01")

    assert len(orders) == 1


@pytest.mark.asyncio
async def test_reset_triggered():
    order_id = uuid.uuid4()
    session = AsyncMock()
    session.execute.return_value = MagicMock()

    repo = OrderRepository(session)
    await repo.reset_triggered(order_id)

    session.execute.assert_called_once()
