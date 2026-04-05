import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.factory import FactoryService
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
    return FactoryService(repo, order_repo, publisher)


@pytest.mark.asyncio
async def test_list_factories_returns_all_with_products(service, repo):
    expected = [MagicMock(), MagicMock()]
    repo.get_all.return_value = expected
    result = await service.list_factories()
    repo.get_all.assert_called_once()
    assert result == expected


@pytest.mark.asyncio
async def test_get_factory_raises_not_found(service, repo):
    repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.get_factory("nonexistent")


@pytest.mark.asyncio
async def test_get_factory_returns_complete_detail(service, repo):
    factory = MagicMock()
    repo.get_by_id.return_value = factory
    result = await service.get_factory("factory-001")
    repo.get_by_id.assert_called_once_with("factory-001")
    assert result == factory


@pytest.mark.asyncio
async def test_create_factory_persists_with_products_and_partners(service, repo):
    data = {
        "id": "factory-001",
        "name": "Fábrica Campinas",
        "lat": -22.9056,
        "lng": -47.0608,
        "products": [{"material_id": "tijolos", "stock": 0.0, "stock_max": 100.0}],
        "partner_warehouses": [{"warehouse_id": "wh-001", "priority": 1}],
    }
    created = MagicMock()
    repo.create.return_value = created
    result = await service.create_factory(data)
    repo.create.assert_called_once_with(data)
    assert result == created


@pytest.mark.asyncio
async def test_update_factory_updates_materials_and_partners(service, repo):
    repo.get_by_id.return_value = MagicMock()
    updated = MagicMock()
    repo.update.return_value = updated
    data = {"name": "Fábrica Campinas Atualizada"}
    result = await service.update_factory("factory-001", data)
    repo.update.assert_called_once_with("factory-001", data)
    assert result == updated


@pytest.mark.asyncio
async def test_update_factory_raises_not_found_when_factory_missing(service, repo):
    repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.update_factory("nonexistent", {"name": "X"})


@pytest.mark.asyncio
async def test_delete_factory_cancels_pending_orders_without_active_route(service, repo, order_repo):
    order_repo.bulk_cancel_by_target.return_value = ["requester-001"]
    await service.delete_factory("factory-001")
    order_repo.bulk_cancel_by_target.assert_called_once_with("factory-001", "target_deleted")
    repo.delete.assert_called_once_with("factory-001")


@pytest.mark.asyncio
async def test_delete_factory_preserves_orders_with_active_truck_route(service, repo, order_repo):
    # bulk_cancel_by_target internally filters orders with active routes;
    # the service only calls the repo and trusts it returns the right set
    order_repo.bulk_cancel_by_target.return_value = []
    await service.delete_factory("factory-001")
    order_repo.bulk_cancel_by_target.assert_called_once_with("factory-001", "target_deleted")
    repo.delete.assert_called_once_with("factory-001")


@pytest.mark.asyncio
async def test_delete_factory_publishes_entity_removed_event(service, repo, order_repo, publisher):
    order_repo.bulk_cancel_by_target.return_value = []
    await service.delete_factory("factory-001")
    publisher.publish_event.assert_called_once_with(
        "entity_removed", {"entity_type": "factory", "entity_id": "factory-001"}
    )


@pytest.mark.asyncio
async def test_adjust_stock_raises_value_error_if_negative_result(service, repo):
    product = MagicMock()
    product.stock = 10.0
    product.stock_max = 100.0
    repo.get_product.return_value = product
    with pytest.raises(ValueError, match="negative"):
        await service.adjust_stock("factory-001", "tijolos", -20.0)


@pytest.mark.asyncio
async def test_adjust_stock_raises_value_error_if_exceeds_stock_max(service, repo):
    product = MagicMock()
    product.stock = 90.0
    product.stock_max = 100.0
    repo.get_product.return_value = product
    with pytest.raises(ValueError, match="stock_max"):
        await service.adjust_stock("factory-001", "tijolos", 20.0)


@pytest.mark.asyncio
async def test_adjust_stock_applies_valid_delta(service, repo):
    product = MagicMock()
    product.stock = 50.0
    product.stock_max = 100.0
    repo.get_product.return_value = product
    await service.adjust_stock("factory-001", "tijolos", 10.0)
    repo.update_product_stock.assert_called_once_with("factory-001", "tijolos", 10.0)
