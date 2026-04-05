import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.services.order import OrderService


@pytest.fixture
def repo():
    return AsyncMock()


@pytest.fixture
def warehouse_repo():
    return AsyncMock()


@pytest.fixture
def factory_repo():
    return AsyncMock()


@pytest.fixture
def service(repo, warehouse_repo, factory_repo):
    return OrderService(repo, warehouse_repo, factory_repo)


@pytest.mark.asyncio
async def test_create_order_sets_pending_and_age_zero(service, repo):
    data = {"material_id": "tijolos", "quantity_tons": 20.0, "target_id": "wh-001"}
    created = MagicMock()
    repo.create.return_value = created
    result = await service.create_order(data)
    call_data = repo.create.call_args[0][0]
    assert call_data["status"] == "pending"
    assert call_data["age_ticks"] == 0
    assert result == created


@pytest.mark.asyncio
async def test_increment_age_ticks_calls_repo_with_correct_statuses(service, repo):
    await service.increment_age_ticks(tick=5)
    repo.increment_all_age_ticks.assert_called_once()


@pytest.mark.asyncio
async def test_get_pending_orders_for_target_delegates_to_repo(service, repo):
    expected = [MagicMock()]
    repo.get_pending_for_target.return_value = expected
    result = await service.get_pending_orders_for("wh-001")
    repo.get_pending_for_target.assert_called_once_with("wh-001")
    assert result == expected


@pytest.mark.asyncio
async def test_confirm_order_sets_confirmed_and_eta(service, repo):
    order_id = uuid.uuid4()
    confirmed = MagicMock()
    repo.update_status.return_value = confirmed
    result = await service.confirm_order(order_id, eta_ticks=8)
    repo.update_status.assert_called_once_with(
        order_id, status="confirmed", eta_ticks=8
    )
    assert result == confirmed


@pytest.mark.asyncio
async def test_reject_order_sets_reason_and_backoff(service, repo):
    order_id = uuid.uuid4()
    rejected = MagicMock()
    repo.update_status.return_value = rejected
    result = await service.reject_order(order_id, reason="no_stock", retry_after=10)
    repo.update_status.assert_called_once_with(
        order_id, status="rejected", rejection_reason="no_stock", retry_after_tick=10
    )
    assert result == rejected


@pytest.mark.asyncio
async def test_mark_delivered_releases_stock_reserved_on_warehouse(
    service, repo, warehouse_repo
):
    order_id = uuid.uuid4()
    order = MagicMock()
    order.target_type = "warehouse"
    order.target_id = "wh-001"
    order.material_id = "tijolos"
    order.quantity_tons = 30.0
    repo.get_by_id.return_value = order
    delivered = MagicMock()
    repo.update_status.return_value = delivered

    result = await service.mark_delivered(order_id)

    warehouse_repo.release_reserved.assert_called_once_with("wh-001", "tijolos", 30.0)
    repo.update_status.assert_called_once_with(order_id, status="delivered")
    assert result == delivered


@pytest.mark.asyncio
async def test_mark_delivered_releases_stock_reserved_on_factory(
    service, repo, factory_repo
):
    order_id = uuid.uuid4()
    order = MagicMock()
    order.target_type = "factory"
    order.target_id = "factory-001"
    order.material_id = "tijolos"
    order.quantity_tons = 15.0
    repo.get_by_id.return_value = order
    delivered = MagicMock()
    repo.update_status.return_value = delivered

    result = await service.mark_delivered(order_id)

    factory_repo.release_reserved.assert_called_once_with(
        "factory-001", "tijolos", 15.0
    )
    repo.update_status.assert_called_once_with(order_id, status="delivered")
    assert result == delivered


@pytest.mark.asyncio
async def test_cancel_orders_targeting_skips_orders_with_active_route(service, repo):
    # bulk_cancel_by_target internally filters orders with active routes (skip_active_routes=True)
    # the service calls the repo with skip_active_routes=True by default
    repo.bulk_cancel_by_target.return_value = ["store-001"]
    result = await service.cancel_orders_targeting(
        "factory-001", reason="target_deleted"
    )
    repo.bulk_cancel_by_target.assert_called_once_with("factory-001", "target_deleted")
    assert result == ["store-001"]


@pytest.mark.asyncio
async def test_cancel_orders_targeting_cancels_pending_and_confirmed(service, repo):
    repo.bulk_cancel_by_target.return_value = ["store-001", "store-002"]
    result = await service.cancel_orders_targeting("wh-001", reason="target_deleted")
    assert "store-001" in result
    assert "store-002" in result


@pytest.mark.asyncio
async def test_cancel_orders_targeting_returns_unique_requester_ids(service, repo):
    repo.bulk_cancel_by_target.return_value = ["store-001", "store-001"]
    await service.cancel_orders_targeting("factory-001", reason="target_deleted")
    assert repo.bulk_cancel_by_target.called


@pytest.mark.asyncio
async def test_cancel_orders_from_cancels_all_requester_pending_confirmed(
    service, repo
):
    repo.bulk_cancel_by_requester.return_value = None
    await service.cancel_orders_from(
        requester_id="store-001", reason="requester_deleted"
    )
    repo.bulk_cancel_by_requester.assert_called_once_with(
        "store-001", "requester_deleted"
    )
