from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_chaos_service
from src.api.models.chaos import ChaosEventCreate, ChaosEventResponse
from src.services import ConflictError, NotFoundError

router = APIRouter(prefix="/chaos", tags=["chaos"])


@router.get("/events")
async def list_active_events(service=Depends(get_chaos_service)):
    events = await service.list_active_events()
    return [ChaosEventResponse.model_validate(e) for e in events]


@router.post("/events", status_code=201)
async def inject_event(body: ChaosEventCreate, current_tick: int, service=Depends(get_chaos_service)):
    result = await service.inject_event(body.model_dump(), current_tick)
    return ChaosEventResponse.model_validate(result)


@router.post("/events/{event_id}/resolve")
async def resolve_event(event_id: UUID, current_tick: int, service=Depends(get_chaos_service)):
    try:
        result = await service.resolve_event(event_id, current_tick)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return ChaosEventResponse.model_validate(result)
