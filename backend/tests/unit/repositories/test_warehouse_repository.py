from unittest.mock import AsyncMock, MagicMock

import pytest

from src.database.models import Warehouse, WarehouseStock
from src.repositories.warehouse import WarehouseRepository


@pytest.mark.asyncio
async def test_get_all_eager_loads_stocks():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        Warehouse(id="w1", name="Armazém Ribeirão Preto", region="Norte"),
        Warehouse(id="w2", name="Armazém Jundiaí", region="Oeste"),
    ]
    session.execute.return_value = result

    repo = WarehouseRepository(session)
    warehouses = await repo.get_all()

    assert len(warehouses) == 2
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_inserts_warehouse_and_stocks():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    repo = WarehouseRepository(session)
    await repo.create({
        "id": "w1",
        "name": "Armazém Ribeirão Preto",
        "lat": -21.17,
        "lng": -47.81,
        "region": "Norte",
        "capacity_total": 1000.0,
        "status": "active",
        "stocks": [
            {"material_id": "m1", "stock": 200.0, "stock_reserved": 0.0, "min_stock": 50.0}
        ],
    })

    assert session.add.call_count >= 2


@pytest.mark.asyncio
async def test_update_stock_applies_delta():
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 1
    session.execute.return_value = result

    repo = WarehouseRepository(session)
    await repo.update_stock(warehouse_id="w1", material_id="m1", delta=-20.0)

    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_total_stock_used_sums_all_products():
    session = AsyncMock()
    result = MagicMock()
    result.scalar.return_value = 30.0
    session.execute.return_value = result

    repo = WarehouseRepository(session)
    total = await repo.get_total_stock_used("w1")

    assert total == 30.0
