from fastapi import APIRouter, Depends

from src.api.dependencies import get_simulation_service, get_world_state_service

router = APIRouter(prefix="/world", tags=["world"])


@router.get("/snapshot")
async def get_snapshot(service=Depends(get_world_state_service)):
    return await service.load()


@router.get("/tick")
async def get_tick(service=Depends(get_simulation_service)):
    status = service.get_status()
    return {
        "current_tick": status["current_tick"],
    }
