from fastapi import APIRouter

from src.api.models.tasks import DecisionSummaryRequest, TaskResponse
from src.workers.tasks.reports import generate_decision_summary, generate_efficiency_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/efficiency", response_model=TaskResponse, status_code=202)
async def post_efficiency_report():
    result = generate_efficiency_report.delay()
    return TaskResponse(task_id=result.id)


@router.post("/decisions", response_model=TaskResponse, status_code=202)
async def post_decision_summary(
    body: DecisionSummaryRequest = DecisionSummaryRequest(),
):
    result = generate_decision_summary.delay()
    return TaskResponse(task_id=result.id)
