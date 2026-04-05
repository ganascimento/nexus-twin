import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.warehouse import WarehouseService
from src.services import NotFoundError


@pytest.fixture
def repo():
    return AsyncMock()


@pytest.fixture
def order_repo():
    return AsyncMock()


@pytest.fixture
def publisher():
    return AsyncMock()


@pytest.fixture
def service(repo, order_repo, publisher):
    return WarehouseService(repo, order_repo, publisher)


@pytest.mark.asyncio
async def test_list_warehouses_returns_all_with_stocks(service, repo):
    expected = [MagicMock(), MagicMock()]
    repo.get_all.return_value = expected
    result = await service.list_warehouses()
    repo.get_all.assert_called_once()
    assert result == expected


@pytest.mark.asyncio
async def test_get_warehouse_raises_not_found(service, repo):
    repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.get_warehouse("nonexistent")


@pytest.mark.asyncio
async def test_get_warehouse_returns_complete_detail(service, repo):
    warehouse = MagicMock()
    repo.get_by_id.return_value = warehouse
    result = await service.get_warehouse("wh-001")
    repo.get_by_id.assert_called_once_with("wh-001")
    assert result == warehouse


@pytest.mark.asyncio
async def test_create_warehouse_with_materials_and_minimums(service, repo):
    data = {
        "id": "wh-001",
        "name": "Armazém Ribeirão Preto",
        "stocks": [{"material_id": "tijolos", "stock": 0.0, "min_stock": 20.0}],
    }
    created = MagicMock()
    repo.create.return_value = created
    result = await service.create_warehouse(data)
    repo.create.assert_called_once_with(data)
    assert result == created


@pytest.mark.asyncio
async def test_update_warehouse_updates_capacity_and_minimums(service, repo):
    repo.get_by_id.return_value = MagicMock()
    updated = MagicMock()
    repo.update.return_value = updated
    data = {"capacity_total": 500.0}
    result = await service.update_warehouse("wh-001", data)
    repo.update.assert_called_once_with("wh-001", data)
    assert result == updated


@pytest.mark.asyncio
async def test_update_warehouse_raises_not_found_when_warehouse_missing(service, repo):
    repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.update_warehouse("nonexistent", {})


@pytest.mark.asyncio
async def test_delete_warehouse_cancels_orders_without_active_route(service, repo, order_repo):
    order_repo.bulk_cancel_by_target.return_value = ["store-001"]
    await service.delete_warehouse("wh-001")
    order_repo.bulk_cancel_by_target.assert_called_once_with("wh-001", "target_deleted")
    repo.delete.assert_called_once_with("wh-001")


@pytest.mark.asyncio
async def test_delete_warehouse_preserves_orders_with_active_truck_route(service, repo, order_repo):
    order_repo.bulk_cancel_by_target.return_value = []
    await service.delete_warehouse("wh-001")
    order_repo.bulk_cancel_by_target.assert_called_once_with("wh-001", "target_deleted")
    repo.delete.assert_called_once_with("wh-001")


@pytest.mark.asyncio
async def test_delete_warehouse_publishes_entity_removed_event(service, repo, order_repo, publisher):
    order_repo.bulk_cancel_by_target.return_value = []
    await service.delete_warehouse("wh-001")
    publisher.publish_event.assert_called_once_with(
        "entity_removed", {"entity_type": "warehouse", "entity_id": "wh-001"}
    )


@pytest.mark.asyncio
async def test_confirm_order_calls_atomic_reserve_and_returns_updated_order(
    service, repo, order_repo
):
    order_id = uuid.uuid4()
    order = MagicMock()
    order.target_id = "wh-001"
    order.material_id = "tijolos"
    order.quantity_tons = 30.0
    order_repo.get_by_id.return_value = order
    repo.atomic_reserve_stock.return_value = True
    confirmed = MagicMock()
    order_repo.update_status.return_value = confirmed

    result = await service.confirm_order(order_id, eta_ticks=5)

    repo.atomic_reserve_stock.assert_called_once_with("wh-001", "tijolos", 30.0)
    order_repo.update_status.assert_called_once_with(order_id, status="confirmed", eta_ticks=5)
    assert result == confirmed


@pytest.mark.asyncio
async def test_confirm_order_returns_none_if_insufficient_stock(service, repo, order_repo):
    order_id = uuid.uuid4()
    order = MagicMock()
    order.target_id = "wh-001"
    order.material_id = "tijolos"
    order.quantity_tons = 200.0
    order_repo.get_by_id.return_value = order
    repo.atomic_reserve_stock.return_value = False

    result = await service.confirm_order(order_id, eta_ticks=5)

    repo.atomic_reserve_stock.assert_called_once_with("wh-001", "tijolos", 200.0)
    order_repo.update_status.assert_not_called()
    assert result is None


@pytest.mark.asyncio
async def test_reject_order_sets_reason_and_returns_order(service, order_repo):
    order_id = uuid.uuid4()
    rejected = MagicMock()
    order_repo.update_status.return_value = rejected

    result = await service.reject_order(order_id, reason="insufficient_stock")

    order_repo.update_status.assert_called_once_with(
        order_id, status="rejected", rejection_reason="insufficient_stock"
    )
    assert result == rejected


@pytest.mark.asyncio
async def test_adjust_stock_raises_value_error_if_negative_result(service, repo):
    stock_entry = MagicMock()
    stock_entry.stock = 5.0
    repo.get_stock.return_value = stock_entry
    with pytest.raises(ValueError, match="negative"):
        await service.adjust_stock("wh-001", "tijolos", -10.0)


@pytest.mark.asyncio
async def test_adjust_stock_applies_valid_delta(service, repo):
    stock_entry = MagicMock()
    stock_entry.stock = 50.0
    repo.get_stock.return_value = stock_entry
    await service.adjust_stock("wh-001", "tijolos", 20.0)
    repo.update_stock.assert_called_once_with("wh-001", "tijolos", 20.0)
