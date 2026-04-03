from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import FactoryProduct, Material, StoreStock, WarehouseStock


class MaterialRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_all(self, active_only: bool = False) -> list[Material]:
        stmt = select(Material)
        if active_only:
            stmt = stmt.where(Material.is_active)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, id: str) -> Material | None:
        stmt = select(Material).where(Material.id == id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Material:
        material = Material(**data)
        self._session.add(material)
        await self._session.flush()
        await self._session.refresh(material)
        return material

    async def update(self, id: str, data: dict) -> Material:
        material = await self.get_by_id(id)
        for key, value in data.items():
            setattr(material, key, value)
        await self._session.flush()
        await self._session.refresh(material)
        return material

    async def has_linked_entities(self, id: str) -> bool:
        stmt = select(
            func.coalesce(
                select(func.count())
                .select_from(FactoryProduct)
                .where(FactoryProduct.material_id == id)
                .scalar_subquery()
                + select(func.count())
                .select_from(WarehouseStock)
                .where(WarehouseStock.material_id == id)
                .scalar_subquery()
                + select(func.count())
                .select_from(StoreStock)
                .where(StoreStock.material_id == id)
                .scalar_subquery(),
                0,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar() > 0
