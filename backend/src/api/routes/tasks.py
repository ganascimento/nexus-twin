from celery.result import AsyncResult
from fastapi import APIRouter

from src.api.models.tasks import TaskStatusResponse
from src.workers.celery_app import celery_app

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    return TaskStatusResponse(
        task_id=task_id,
        status=result.status,
        result=result.result if result.status == "SUCCESS" else None,
        error=str(result.result) if result.status == "FAILURE" else None,
    )
