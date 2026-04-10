from pydantic import BaseModel


class TaskResponse(BaseModel):
    task_id: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: dict | list | None = None
    error: str | None = None


class DecisionSummaryRequest(BaseModel):
    ticks: int = 24


class DecisionExportRequest(BaseModel):
    entity_id: str | None = None
    limit: int | None = None
