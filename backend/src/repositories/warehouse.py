from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Warehouse, WarehouseStock


class WarehouseRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_all(self) -> list[Warehouse]:
        stmt = select(Warehouse)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, id: str) -> Warehouse | None:
        stmt = select(Warehouse).where(Warehouse.id == id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Warehouse:
        payload = data.copy()
        stocks = payload.pop("stocks", [])
        warehouse = Warehouse(**payload)
        self._session.add(warehouse)
        for s in stocks:
            self._session.add(WarehouseStock(warehouse_id=warehouse.id, **s))
        await self._session.flush()
        await self._session.refresh(warehouse)
        return warehouse

    async def update(self, id: str, data: dict) -> Warehouse:
        payload = data.copy()
        stocks = payload.pop("stocks", None)

        warehouse = await self.get_by_id(id)
        for key, value in payload.items():
            setattr(warehouse, key, value)

        if stocks is not None:
            await self._session.execute(
                delete(WarehouseStock).where(WarehouseStock.warehouse_id == id)
            )
            for s in stocks:
                self._session.add(WarehouseStock(warehouse_id=id, **s))

        await self._session.flush()
        await self._session.refresh(warehouse)
        return warehouse

    async def delete(self, id: str) -> None:
        await self._session.execute(
            delete(WarehouseStock).where(WarehouseStock.warehouse_id == id)
        )
        await self._session.execute(delete(Warehouse).where(Warehouse.id == id))

    async def update_stock(
        self, warehouse_id: str, material_id: str, delta: float
    ) -> None:
        stmt = (
            update(WarehouseStock)
            .where(
                WarehouseStock.warehouse_id == warehouse_id,
                WarehouseStock.material_id == material_id,
            )
            .values(stock=WarehouseStock.stock + delta)
        )
        await self._session.execute(stmt)

    async def get_total_stock_used(self, warehouse_id: str) -> float:
        stmt = select(func.coalesce(func.sum(WarehouseStock.stock), 0)).where(
            WarehouseStock.warehouse_id == warehouse_id
        )
        result = await self._session.execute(stmt)
        return result.scalar()
