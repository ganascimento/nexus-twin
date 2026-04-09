from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChaosEventCreate(BaseModel):
    event_type: str
    entity_type: str
    entity_id: str
    payload: dict = {}


class ChaosEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    source: str
    entity_type: str
    entity_id: str
    payload: dict
    status: str
    tick_start: int
    tick_end: int | None = None
