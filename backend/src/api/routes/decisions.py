from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_agent_decision_repo
from src.api.models.decisions import DecisionResponse

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get("/")
async def list_decisions(
    entity_id: str | None = None,
    limit: int = 50,
    repo=Depends(get_agent_decision_repo),
):
    decisions = await repo.get_all(entity_id=entity_id, limit=limit)
    return [DecisionResponse.model_validate(d) for d in decisions]


@router.get("/{entity_id}")
async def get_decisions_for_entity(
    entity_id: str,
    limit: int = 50,
    repo=Depends(get_agent_decision_repo),
):
    decisions = await repo.get_recent_by_entity(entity_id, limit)
    if not decisions:
        raise HTTPException(status_code=404, detail=f"No decisions found for entity '{entity_id}'")
    return [DecisionResponse.model_validate(d) for d in decisions]
