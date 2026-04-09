from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_id: str
    agent_type: str
    action: str
    event_type: str
    payload: dict
    tick: int
    reasoning: str | None = None
