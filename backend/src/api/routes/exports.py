from fastapi import APIRouter

from src.api.models.tasks import DecisionExportRequest, TaskResponse
from src.workers.tasks.exports import (
    export_decision_history,
    export_event_history,
    export_world_snapshot,
)

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("/decisions", response_model=TaskResponse, status_code=202)
async def post_export_decisions(body: DecisionExportRequest = DecisionExportRequest()):
    result = export_decision_history.delay(entity_id=body.entity_id, limit=body.limit)
    return TaskResponse(task_id=result.id)


@router.post("/events", response_model=TaskResponse, status_code=202)
async def post_export_events():
    result = export_event_history.delay()
    return TaskResponse(task_id=result.id)


@router.post("/world-snapshot", response_model=TaskResponse, status_code=202)
async def post_export_world_snapshot():
    result = export_world_snapshot.delay()
    return TaskResponse(task_id=result.id)
