from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import get_db


async def get_simulation_service():
    raise NotImplementedError


async def get_world_state_service():
    raise NotImplementedError


async def get_material_service(db: AsyncSession = Depends(get_db)):
    from src.repositories.material import MaterialRepository
    from src.services.material import MaterialService

    return MaterialService(MaterialRepository(db))


async def get_factory_service(db: AsyncSession = Depends(get_db)):
    raise NotImplementedError


async def get_warehouse_service(db: AsyncSession = Depends(get_db)):
    raise NotImplementedError


async def get_store_service(db: AsyncSession = Depends(get_db)):
    raise NotImplementedError


async def get_truck_service(db: AsyncSession = Depends(get_db)):
    raise NotImplementedError


async def get_chaos_service(db: AsyncSession = Depends(get_db)):
    raise NotImplementedError


async def get_agent_decision_repo(db: AsyncSession = Depends(get_db)):
    from src.repositories.agent_decision import AgentDecisionRepository

    return AgentDecisionRepository(db)
