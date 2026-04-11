from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import get_db


async def get_material_service(db: AsyncSession = Depends(get_db)):
    from src.repositories.material import MaterialRepository
    from src.services.material import MaterialService

    return MaterialService(MaterialRepository(db))


async def get_factory_service(db: AsyncSession = Depends(get_db)):
    from src.repositories.factory import FactoryRepository
    from src.repositories.order import OrderRepository
    from src.services.factory import FactoryService

    factory_repo = FactoryRepository(db)
    order_repo = OrderRepository(db)
    publisher = _RedisPublisher(db)
    return FactoryService(factory_repo, order_repo, publisher)


async def get_warehouse_service(db: AsyncSession = Depends(get_db)):
    from src.repositories.order import OrderRepository
    from src.repositories.warehouse import WarehouseRepository
    from src.services.warehouse import WarehouseService

    warehouse_repo = WarehouseRepository(db)
    order_repo = OrderRepository(db)
    publisher = _RedisPublisher(db)
    return WarehouseService(warehouse_repo, order_repo, publisher)


async def get_store_service(db: AsyncSession = Depends(get_db)):
    from src.repositories.factory import FactoryRepository
    from src.repositories.order import OrderRepository
    from src.repositories.store import StoreRepository
    from src.repositories.warehouse import WarehouseRepository
    from src.services.order import OrderService
    from src.services.store import StoreService

    store_repo = StoreRepository(db)
    order_repo = OrderRepository(db)
    warehouse_repo = WarehouseRepository(db)
    factory_repo = FactoryRepository(db)
    order_service = OrderService(order_repo, warehouse_repo, factory_repo)
    publisher = _RedisPublisher(db)
    return StoreService(store_repo, order_service, publisher)


async def get_truck_service(db: AsyncSession = Depends(get_db)):
    from src.repositories.truck import TruckRepository
    from src.services.truck import TruckService

    truck_repo = TruckRepository(db)
    publisher = _RedisPublisher(db)
    return TruckService(truck_repo, publisher)


async def get_chaos_service(db: AsyncSession = Depends(get_db)):
    from src.repositories.event import EventRepository
    from src.services.chaos import ChaosService

    event_repo = EventRepository(db)
    return ChaosService(event_repo, db)


async def get_simulation_service(request: Request):
    return request.app.state.simulation_service


async def get_world_state_service(db: AsyncSession = Depends(get_db)):
    from src.services.world_state import WorldStateService

    return WorldStateService(db)


async def get_agent_decision_repo(db: AsyncSession = Depends(get_db)):
    from src.repositories.agent_decision import AgentDecisionRepository

    return AgentDecisionRepository(db)


class _RedisPublisher:
    def __init__(self, db_session):
        self._db = db_session

    async def publish_event(self, event_type: str, payload: dict) -> None:
        from loguru import logger
        logger.debug("Publisher event: {} {}", event_type, payload)

    async def publish_decision(self, entity_id: str, entity_type: str, decision: dict) -> None:
        from loguru import logger
        logger.debug("Publisher decision: {} {} {}", entity_id, entity_type, decision)
