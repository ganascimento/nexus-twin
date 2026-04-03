from unittest.mock import AsyncMock, MagicMock

import pytest
from src.database.models import Store
from src.repositories.store import StoreRepository


@pytest.mark.asyncio
async def test_get_all_eager_loads_stocks():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        Store(id="s1", name="Loja SP Centro"),
        Store(id="s2", name="Loja SP Sul"),
    ]
    session.execute.return_value = result

    repo = StoreRepository(session)
    stores = await repo.get_all()

    assert len(stores) == 2
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_inserts_store_and_stocks():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    repo = StoreRepository(session)
    await repo.create(
        {
            "id": "s1",
            "name": "Loja SP Centro",
            "lat": -23.55,
            "lng": -46.63,
            "status": "active",
            "stocks": [
                {
                    "material_id": "m1",
                    "stock": 50.0,
                    "demand_rate": 5.0,
                    "reorder_point": 10.0,
                }
            ],
        }
    )

    assert session.add.call_count >= 2


@pytest.mark.asyncio
async def test_update_stock_applies_delta():
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 1
    session.execute.return_value = result

    repo = StoreRepository(session)
    await repo.update_stock(store_id="s1", material_id="m1", delta=-5.0)

    session.execute.assert_called_once()
