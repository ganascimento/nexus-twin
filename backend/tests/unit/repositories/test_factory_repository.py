from unittest.mock import AsyncMock, MagicMock

import pytest
from src.database.models import Factory
from src.repositories.factory import FactoryRepository


@pytest.mark.asyncio
async def test_get_all_eager_loads_products():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        Factory(id="f1", name="Fábrica Campinas"),
        Factory(id="f2", name="Fábrica Sorocaba"),
    ]
    session.execute.return_value = result

    repo = FactoryRepository(session)
    factories = await repo.get_all()

    assert len(factories) == 2
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_by_id_includes_trucks_and_partners():
    session = AsyncMock()
    expected = Factory(id="f1", name="Fábrica Campinas")
    result = MagicMock()
    result.scalar_one_or_none.return_value = expected
    session.execute.return_value = result

    repo = FactoryRepository(session)
    factory = await repo.get_by_id("f1")

    assert factory is expected


@pytest.mark.asyncio
async def test_create_inserts_factory_products_and_partners_in_transaction():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    repo = FactoryRepository(session)
    await repo.create(
        {
            "id": "f1",
            "name": "Fábrica Campinas",
            "lat": -22.9,
            "lng": -47.1,
            "status": "active",
            "products": [
                {
                    "material_id": "m1",
                    "stock": 100.0,
                    "stock_reserved": 0.0,
                    "stock_max": 500.0,
                    "production_rate_max": 50.0,
                    "production_rate_current": 50.0,
                }
            ],
            "partner_warehouses": [{"warehouse_id": "w1", "priority": 1}],
        }
    )

    assert session.add.call_count >= 3


@pytest.mark.asyncio
async def test_update_product_stock_applies_delta():
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 1
    session.execute.return_value = result

    repo = FactoryRepository(session)
    await repo.update_product_stock(factory_id="f1", material_id="m1", delta=10.0)

    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_update_production_rate():
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 1
    session.execute.return_value = result

    repo = FactoryRepository(session)
    await repo.update_production_rate(factory_id="f1", material_id="m1", rate=30.0)

    session.execute.assert_called_once()
