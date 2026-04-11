from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database.models import (
    Factory,
    FactoryPartnerWarehouse,
    FactoryProduct,
    Material,
    Store,
    StoreStock,
    Truck,
    Warehouse,
    WarehouseStock,
)
from src.world.entities.factory import (
    Factory as FactoryEntity,
    FactoryPartnerWarehouse as FactoryPartnerWarehouseEntity,
    FactoryProduct as FactoryProductEntity,
)
from src.world.entities.material import Material as MaterialEntity
from src.world.entities.store import Store as StoreEntity, StoreStock as StoreStockEntity
from src.world.entities.truck import Truck as TruckEntity
from src.world.entities.warehouse import (
    Warehouse as WarehouseEntity,
    WarehouseStock as WarehouseStockEntity,
)
from src.world.state import WorldState

SIMULATED_START = datetime(2025, 1, 1, tzinfo=timezone.utc)


class WorldStateService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def load(self, tick: int = 0) -> WorldState:
        materials = await self._load_materials()
        factories = await self._load_factories()
        warehouses = await self._load_warehouses()
        stores = await self._load_stores()
        trucks = await self._load_trucks()

        return WorldState(
            tick=tick,
            simulated_timestamp=SIMULATED_START + timedelta(hours=tick),
            materials=materials,
            factories=factories,
            warehouses=warehouses,
            stores=stores,
            trucks=trucks,
        )

    async def _load_materials(self) -> list[MaterialEntity]:
        result = await self._session.execute(select(Material))
        rows = result.scalars().all()
        return [
            MaterialEntity(id=m.id, name=m.name, is_active=m.is_active) for m in rows
        ]

    async def _load_factories(self) -> list[FactoryEntity]:
        result = await self._session.execute(select(Factory))
        factories = result.scalars().all()

        entities = []
        for f in factories:
            prod_result = await self._session.execute(
                select(FactoryProduct).where(FactoryProduct.factory_id == f.id)
            )
            products = {
                p.material_id: FactoryProductEntity(
                    stock=p.stock,
                    stock_reserved=p.stock_reserved,
                    stock_max=p.stock_max,
                    production_rate_max=p.production_rate_max,
                    production_rate_current=p.production_rate_current,
                )
                for p in prod_result.scalars().all()
            }

            partner_result = await self._session.execute(
                select(FactoryPartnerWarehouse).where(
                    FactoryPartnerWarehouse.factory_id == f.id
                )
            )
            partners = [
                FactoryPartnerWarehouseEntity(warehouse_id=pw.warehouse_id)
                for pw in partner_result.scalars().all()
            ]

            entities.append(
                FactoryEntity(
                    id=f.id,
                    name=f.name,
                    lat=f.lat,
                    lng=f.lng,
                    status=f.status,
                    products=products,
                    partner_warehouses=partners,
                )
            )
        return entities

    async def _load_warehouses(self) -> list[WarehouseEntity]:
        result = await self._session.execute(select(Warehouse))
        warehouses = result.scalars().all()

        entities = []
        for w in warehouses:
            stock_result = await self._session.execute(
                select(WarehouseStock).where(WarehouseStock.warehouse_id == w.id)
            )
            stocks = {
                s.material_id: WarehouseStockEntity(
                    stock=s.stock,
                    stock_reserved=s.stock_reserved,
                    min_stock=s.min_stock,
                )
                for s in stock_result.scalars().all()
            }
            entities.append(
                WarehouseEntity(
                    id=w.id,
                    name=w.name,
                    lat=w.lat,
                    lng=w.lng,
                    region=w.region,
                    capacity_total=w.capacity_total,
                    status=w.status,
                    stocks=stocks,
                )
            )
        return entities

    async def _load_stores(self) -> list[StoreEntity]:
        result = await self._session.execute(select(Store))
        stores = result.scalars().all()

        entities = []
        for s in stores:
            stock_result = await self._session.execute(
                select(StoreStock).where(StoreStock.store_id == s.id)
            )
            stocks = {
                st.material_id: StoreStockEntity(
                    stock=st.stock,
                    demand_rate=st.demand_rate,
                    reorder_point=st.reorder_point,
                )
                for st in stock_result.scalars().all()
            }
            entities.append(
                StoreEntity(
                    id=s.id,
                    name=s.name,
                    lat=s.lat,
                    lng=s.lng,
                    region=s.region,
                    status=s.status,
                    stocks=stocks,
                )
            )
        return entities

    async def _load_trucks(self) -> list[TruckEntity]:
        result = await self._session.execute(select(Truck))
        trucks = result.scalars().all()
        return [
            TruckEntity(
                id=t.id,
                name=t.name,
                truck_type=t.truck_type,
                factory_id=t.factory_id,
                capacity_tons=t.capacity_tons,
                current_lat=t.current_lat,
                current_lng=t.current_lng,
                status=t.status,
                degradation=t.degradation,
                breakdown_risk=t.breakdown_risk,
                cargo=t.cargo,
                active_route=None,
            )
            for t in trucks
        ]
