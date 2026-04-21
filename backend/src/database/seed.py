from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.database.models.material import Material
from src.database.models.factory import Factory, FactoryProduct, FactoryPartnerWarehouse
from src.database.models.warehouse import Warehouse, WarehouseStock
from src.database.models.store import Store, StoreStock
from src.database.models.truck import Truck


async def seed_default_world(session: AsyncSession) -> None:
    await session.execute(
        pg_insert(Material).values([
            {"id": "tijolos",   "name": "Tijolos",    "is_active": True},
            {"id": "vergalhao", "name": "Vergalhão",  "is_active": True},
            {"id": "cimento",   "name": "Cimento",    "is_active": True},
        ]).on_conflict_do_nothing(index_elements=["id"])
    )

    await session.execute(
        pg_insert(Factory).values([
            {"id": "factory-001", "name": "Tijolaria Anhanguera", "lat": -22.9099, "lng": -47.0626, "status": "operating"},
            {"id": "factory-002", "name": "Aciaria Sorocabana",   "lat": -23.5015, "lng": -47.4526, "status": "operating"},
            {"id": "factory-003", "name": "Cimenteira Paulista",  "lat": -23.5472, "lng": -47.4385, "status": "operating"},
        ]).on_conflict_do_nothing(index_elements=["id"])
    )

    await session.execute(
        pg_insert(Warehouse).values([
            {"id": "warehouse-001", "name": "Hub Norte",        "lat": -21.1784, "lng": -47.8108, "region": "Interior Norte",   "capacity_total": 800,  "status": "operating"},
            {"id": "warehouse-002", "name": "Hub Centro-Oeste", "lat": -23.1864, "lng": -46.8964, "region": "Grande SP Oeste",  "capacity_total": 1000, "status": "operating"},
            {"id": "warehouse-003", "name": "Hub Leste",        "lat": -23.5227, "lng": -46.1857, "region": "Grande SP Leste",  "capacity_total": 600,  "status": "operating"},
        ]).on_conflict_do_nothing(index_elements=["id"])
    )

    await session.execute(
        pg_insert(FactoryProduct).values([
            {"factory_id": "factory-001", "material_id": "tijolos",   "stock": 12,   "stock_reserved": 0, "stock_max": 30,   "production_rate_max": 2,   "production_rate_current": 0},
            {"factory_id": "factory-002", "material_id": "vergalhao", "stock": 2000, "stock_reserved": 0, "stock_max": 5000, "production_rate_max": 120, "production_rate_current": 0},
            {"factory_id": "factory-003", "material_id": "cimento",   "stock": 400,  "stock_reserved": 0, "stock_max": 750,  "production_rate_max": 30,  "production_rate_current": 0},
        ]).on_conflict_do_nothing(index_elements=["factory_id", "material_id"])
    )

    await session.execute(
        pg_insert(FactoryPartnerWarehouse).values([
            {"factory_id": "factory-001", "warehouse_id": "warehouse-002", "priority": 1},
            {"factory_id": "factory-001", "warehouse_id": "warehouse-003", "priority": 2},
            {"factory_id": "factory-002", "warehouse_id": "warehouse-002", "priority": 1},
            {"factory_id": "factory-002", "warehouse_id": "warehouse-001", "priority": 2},
            {"factory_id": "factory-003", "warehouse_id": "warehouse-001", "priority": 1},
            {"factory_id": "factory-003", "warehouse_id": "warehouse-002", "priority": 2},
            {"factory_id": "factory-003", "warehouse_id": "warehouse-003", "priority": 3},
        ]).on_conflict_do_nothing(index_elements=["factory_id", "warehouse_id"])
    )

    await session.execute(
        pg_insert(WarehouseStock).values([
            {"warehouse_id": "warehouse-001", "material_id": "vergalhao", "stock": 500, "stock_reserved": 0, "min_stock": 100},
            {"warehouse_id": "warehouse-001", "material_id": "cimento",   "stock": 100, "stock_reserved": 0, "min_stock": 20},
            {"warehouse_id": "warehouse-002", "material_id": "tijolos",   "stock": 10,  "stock_reserved": 0, "min_stock": 2},
            {"warehouse_id": "warehouse-002", "material_id": "vergalhao", "stock": 800, "stock_reserved": 0, "min_stock": 150},
            {"warehouse_id": "warehouse-002", "material_id": "cimento",   "stock": 150, "stock_reserved": 0, "min_stock": 25},
            {"warehouse_id": "warehouse-003", "material_id": "tijolos",   "stock": 6,   "stock_reserved": 0, "min_stock": 1},
            {"warehouse_id": "warehouse-003", "material_id": "vergalhao", "stock": 400, "stock_reserved": 0, "min_stock": 80},
            {"warehouse_id": "warehouse-003", "material_id": "cimento",   "stock": 75,  "stock_reserved": 0, "min_stock": 15},
        ]).on_conflict_do_nothing(index_elements=["warehouse_id", "material_id"])
    )

    await session.execute(
        pg_insert(Store).values([
            {"id": "store-001", "name": "Constrular Centro",     "lat": -23.5505, "lng": -46.6333, "status": "open"},
            {"id": "store-002", "name": "Constrular Zona Leste", "lat": -23.5432, "lng": -46.4506, "status": "open"},
            {"id": "store-003", "name": "Constrular Campinas",   "lat": -22.9099, "lng": -47.0626, "status": "open"},
            {"id": "store-004", "name": "Material Norte",        "lat": -21.1784, "lng": -47.8108, "status": "open"},
            {"id": "store-005", "name": "Depósito Paulista",     "lat": -23.4628, "lng": -46.5333, "status": "open"},
        ]).on_conflict_do_nothing(index_elements=["id"])
    )

    await session.execute(
        pg_insert(StoreStock).values([
            {"store_id": "store-001", "material_id": "tijolos",   "stock": 1.5,  "demand_rate": 0.5,  "reorder_point": 1.0},
            {"store_id": "store-001", "material_id": "vergalhao", "stock": 90,   "demand_rate": 30,   "reorder_point": 60},
            {"store_id": "store-001", "material_id": "cimento",   "stock": 22.5, "demand_rate": 7.5,  "reorder_point": 15},
            {"store_id": "store-002", "material_id": "tijolos",   "stock": 1.0,  "demand_rate": 0.4,  "reorder_point": 1.0},
            {"store_id": "store-002", "material_id": "cimento",   "stock": 15,   "demand_rate": 5,    "reorder_point": 10},
            {"store_id": "store-003", "material_id": "tijolos",   "stock": 1.0,  "demand_rate": 0.3,  "reorder_point": 1.0},
            {"store_id": "store-003", "material_id": "vergalhao", "stock": 60,   "demand_rate": 20,   "reorder_point": 40},
            {"store_id": "store-004", "material_id": "vergalhao", "stock": 75,   "demand_rate": 25,   "reorder_point": 50},
            {"store_id": "store-004", "material_id": "cimento",   "stock": 18,   "demand_rate": 6,    "reorder_point": 12},
            {"store_id": "store-005", "material_id": "tijolos",   "stock": 1.5,  "demand_rate": 0.5,  "reorder_point": 1.0},
            {"store_id": "store-005", "material_id": "cimento",   "stock": 84,   "demand_rate": 28,   "reorder_point": 56},
            {"store_id": "store-005", "material_id": "vergalhao", "stock": 20,   "demand_rate": 6.5,  "reorder_point": 13},
        ]).on_conflict_do_nothing(index_elements=["store_id", "material_id"])
    )

    await session.execute(
        pg_insert(Truck).values([
            {"id": "truck-001", "truck_type": "proprietario", "capacity_tons": 15, "base_lat": -22.9099, "base_lng": -47.0626, "current_lat": -22.9099, "current_lng": -47.0626, "degradation": 0.20, "breakdown_risk": 0.0, "status": "idle", "factory_id": "factory-001", "cargo": None, "active_route_id": None},
            {"id": "truck-002", "truck_type": "proprietario", "capacity_tons": 20, "base_lat": -23.5472, "base_lng": -47.4385, "current_lat": -23.5472, "current_lng": -47.4385, "degradation": 0.15, "breakdown_risk": 0.0, "status": "idle", "factory_id": "factory-003", "cargo": None, "active_route_id": None},
            {"id": "truck-004", "truck_type": "terceiro",     "capacity_tons": 18, "base_lat": -23.5505, "base_lng": -46.6333, "current_lat": -23.5505, "current_lng": -46.6333, "degradation": 0.10, "breakdown_risk": 0.0, "status": "idle", "factory_id": None,         "cargo": None, "active_route_id": None},
            {"id": "truck-005", "truck_type": "terceiro",     "capacity_tons": 22, "base_lat": -22.9099, "base_lng": -47.0626, "current_lat": -22.9099, "current_lng": -47.0626, "degradation": 0.25, "breakdown_risk": 0.0, "status": "idle", "factory_id": None,         "cargo": None, "active_route_id": None},
            {"id": "truck-006", "truck_type": "terceiro",     "capacity_tons": 10, "base_lat": -21.1784, "base_lng": -47.8108, "current_lat": -21.1784, "current_lng": -47.8108, "degradation": 0.40, "breakdown_risk": 0.0, "status": "idle", "factory_id": None,         "cargo": None, "active_route_id": None},
            {"id": "truck-007", "truck_type": "terceiro",     "capacity_tons": 6,  "base_lat": -23.5432, "base_lng": -46.4506, "current_lat": -23.5432, "current_lng": -46.4506, "degradation": 0.05, "breakdown_risk": 0.0, "status": "idle", "factory_id": None,         "cargo": None, "active_route_id": None},
        ]).on_conflict_do_nothing(index_elements=["id"])
    )
