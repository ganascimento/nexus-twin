from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Store, StoreStock


class StoreRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_all(self) -> list[Store]:
        stmt = select(Store)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, id: str) -> Store | None:
        stmt = select(Store).where(Store.id == id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Store:
        payload = data.copy()
        stocks = payload.pop("stocks", [])
        store = Store(**payload)
        self._session.add(store)
        for s in stocks:
            self._session.add(StoreStock(store_id=store.id, **s))
        await self._session.flush()
        await self._session.refresh(store)
        return store

    async def update(self, id: str, data: dict) -> Store:
        payload = data.copy()
        stocks = payload.pop("stocks", None)

        store = await self.get_by_id(id)
        for key, value in payload.items():
            setattr(store, key, value)

        if stocks is not None:
            await self._session.execute(
                delete(StoreStock).where(StoreStock.store_id == id)
            )
            for s in stocks:
                self._session.add(StoreStock(store_id=id, **s))

        await self._session.flush()
        await self._session.refresh(store)
        return store

    async def delete(self, id: str) -> None:
        await self._session.execute(delete(StoreStock).where(StoreStock.store_id == id))
        await self._session.execute(delete(Store).where(Store.id == id))

    async def update_stock(self, store_id: str, material_id: str, delta: float) -> None:
        stmt = (
            update(StoreStock)
            .where(
                StoreStock.store_id == store_id, StoreStock.material_id == material_id
            )
            .values(stock=StoreStock.stock + delta)
        )
        await self._session.execute(stmt)
