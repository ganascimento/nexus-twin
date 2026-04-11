from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_simulation_service
from src.api.models.simulation import SpeedUpdate
from src.services import ConflictError

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/start")
async def start_simulation(service=Depends(get_simulation_service)):
    await service.start()
    return {"status": "started"}


@router.post("/stop")
async def stop_simulation(service=Depends(get_simulation_service)):
    await service.stop()
    return {"status": "stopped"}


@router.post("/tick")
async def advance_tick(service=Depends(get_simulation_service)):
    try:
        result = await service.advance_tick()
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return result


@router.get("/status")
async def get_status(service=Depends(get_simulation_service)):
    return service.get_status()


@router.patch("/speed")
async def set_speed(body: SpeedUpdate, service=Depends(get_simulation_service)):
    try:
        service.set_tick_interval(body.tick_interval_seconds)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "updated"}
