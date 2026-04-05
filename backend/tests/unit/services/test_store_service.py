import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.store import StoreService
from src.services import NotFoundError


@pytest.fixture
def repo():
    return AsyncMock()


@pytest.fixture
def order_service():
    return AsyncMock()


@pytest.fixture
def publisher():
    return AsyncMock()


@pytest.fixture
def service(repo, order_service, publisher):
    return StoreService(repo, order_service, publisher)


@pytest.mark.asyncio
async def test_list_stores_returns_all_with_stocks(service, repo):
    expected = [MagicMock(), MagicMock()]
    repo.get_all.return_value = expected
    result = await service.list_stores()
    repo.get_all.assert_called_once()
    assert result == expected


@pytest.mark.asyncio
async def test_get_store_raises_not_found(service, repo):
    repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.get_store("nonexistent")


@pytest.mark.asyncio
async def test_get_store_returns_complete_detail(service, repo):
    store = MagicMock()
    repo.get_by_id.return_value = store
    result = await service.get_store("store-001")
    repo.get_by_id.assert_called_once_with("store-001")
    assert result == store


@pytest.mark.asyncio
async def test_create_store_with_materials_demand_and_reorder(service, repo):
    data = {
        "id": "store-001",
        "name": "Loja SP Capital",
        "stocks": [
            {"material_id": "tijolos", "stock": 0.0, "demand_rate": 2.0, "reorder_point": 10.0}
        ],
    }
    created = MagicMock()
    repo.create.return_value = created
    result = await service.create_store(data)
    repo.create.assert_called_once_with(data)
    assert result == created


@pytest.mark.asyncio
async def test_update_store_updates_demand_and_reorder(service, repo):
    repo.get_by_id.return_value = MagicMock()
    updated = MagicMock()
    repo.update.return_value = updated
    data = {"stocks": [{"material_id": "tijolos", "demand_rate": 3.0, "reorder_point": 15.0}]}
    result = await service.update_store("store-001", data)
    repo.update.assert_called_once_with("store-001", data)
    assert result == updated


@pytest.mark.asyncio
async def test_update_store_raises_not_found_when_store_missing(service, repo):
    repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.update_store("nonexistent", {})


@pytest.mark.asyncio
async def test_delete_store_calls_cancel_orders_from_with_correct_args(
    service, repo, order_service
):
    await service.delete_store("store-001")
    order_service.cancel_orders_from.assert_called_once_with(
        requester_id="store-001", reason="requester_deleted"
    )
    repo.delete.assert_called_once_with("store-001")


@pytest.mark.asyncio
async def test_delete_store_publishes_entity_removed_event(service, repo, order_service, publisher):
    await service.delete_store("store-001")
    publisher.publish_event.assert_called_once_with(
        "entity_removed", {"entity_type": "store", "entity_id": "store-001"}
    )


@pytest.mark.asyncio
async def test_adjust_stock_raises_value_error_if_negative_result(service, repo):
    stock_entry = MagicMock()
    stock_entry.stock = 5.0
    repo.get_stock.return_value = stock_entry
    with pytest.raises(ValueError, match="negative"):
        await service.adjust_stock("store-001", "tijolos", -10.0)


@pytest.mark.asyncio
async def test_adjust_stock_applies_valid_delta(service, repo):
    stock_entry = MagicMock()
    stock_entry.stock = 20.0
    repo.get_stock.return_value = stock_entry
    await service.adjust_stock("store-001", "tijolos", 5.0)
    repo.update_stock.assert_called_once_with("store-001", "tijolos", 5.0)


@pytest.mark.asyncio
async def test_create_order_delegates_to_order_service(service, order_service):
    data = {"material_id": "tijolos", "quantity_tons": 20.0}
    created = MagicMock()
    order_service.create_order.return_value = created
    result = await service.create_order(data)
    order_service.create_order.assert_called_once_with(data)
    assert result == created
