from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Factory, FactoryPartnerWarehouse, FactoryProduct, Warehouse


class FactoryRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_all(self) -> list[Factory]:
        stmt = select(Factory)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, id: str) -> Factory | None:
        stmt = select(Factory).where(Factory.id == id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Factory:
        payload = data.copy()
        products = payload.pop("products", [])
        partner_warehouses = payload.pop("partner_warehouses", [])
        factory = Factory(**payload)
        self._session.add(factory)
        for p in products:
            self._session.add(FactoryProduct(factory_id=factory.id, **p))
        for pw in partner_warehouses:
            self._session.add(FactoryPartnerWarehouse(factory_id=factory.id, **pw))
        await self._session.flush()
        await self._session.refresh(factory)
        return factory

    async def update(self, id: str, data: dict) -> Factory:
        payload = data.copy()
        products = payload.pop("products", None)
        partner_warehouses = payload.pop("partner_warehouses", None)

        factory = await self.get_by_id(id)
        for key, value in payload.items():
            setattr(factory, key, value)

        if products is not None:
            await self._session.execute(
                delete(FactoryProduct).where(FactoryProduct.factory_id == id)
            )
            for p in products:
                self._session.add(FactoryProduct(factory_id=id, **p))

        if partner_warehouses is not None:
            await self._session.execute(
                delete(FactoryPartnerWarehouse).where(
                    FactoryPartnerWarehouse.factory_id == id
                )
            )
            for pw in partner_warehouses:
                self._session.add(FactoryPartnerWarehouse(factory_id=id, **pw))

        await self._session.flush()
        await self._session.refresh(factory)
        return factory

    async def delete(self, id: str) -> None:
        await self._session.execute(
            delete(FactoryPartnerWarehouse).where(
                FactoryPartnerWarehouse.factory_id == id
            )
        )
        await self._session.execute(
            delete(FactoryProduct).where(FactoryProduct.factory_id == id)
        )
        await self._session.execute(delete(Factory).where(Factory.id == id))

    async def update_product_stock(
        self, factory_id: str, material_id: str, delta: float
    ) -> None:
        stmt = (
            update(FactoryProduct)
            .where(
                FactoryProduct.factory_id == factory_id,
                FactoryProduct.material_id == material_id,
            )
            .values(stock=FactoryProduct.stock + delta)
        )
        await self._session.execute(stmt)

    async def get_product(self, factory_id: str, material_id: str):
        result = await self._session.execute(
            select(FactoryProduct).where(
                FactoryProduct.factory_id == factory_id,
                FactoryProduct.material_id == material_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_production_rate(
        self, factory_id: str, material_id: str, rate: float
    ) -> None:
        stmt = (
            update(FactoryProduct)
            .where(
                FactoryProduct.factory_id == factory_id,
                FactoryProduct.material_id == material_id,
            )
            .values(production_rate_current=rate)
        )
        await self._session.execute(stmt)

    async def release_reserved(self, factory_id: str, material_id: str, quantity: float) -> None:
        await self._session.execute(
            update(FactoryProduct)
            .where(
                FactoryProduct.factory_id == factory_id,
                FactoryProduct.material_id == material_id,
            )
            .values(stock_reserved=FactoryProduct.stock_reserved - quantity)
        )

    async def get_partner_warehouses(self, factory_id: str) -> list[Warehouse]:
        stmt = (
            select(Warehouse)
            .join(FactoryPartnerWarehouse, FactoryPartnerWarehouse.warehouse_id == Warehouse.id)
            .where(FactoryPartnerWarehouse.factory_id == factory_id)
            .order_by(FactoryPartnerWarehouse.priority)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_partner_for_warehouse(self, warehouse_id: str) -> list[Factory]:
        stmt = (
            select(Factory)
            .join(FactoryPartnerWarehouse, FactoryPartnerWarehouse.factory_id == Factory.id)
            .where(FactoryPartnerWarehouse.warehouse_id == warehouse_id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
