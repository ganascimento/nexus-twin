from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import AgentDecision


class AgentDecisionRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, data: dict) -> AgentDecision:
        decision = AgentDecision(**data)
        self._session.add(decision)
        await self._session.flush()
        await self._session.refresh(decision)
        return decision

    async def get_recent_by_entity(
        self, entity_id: str, limit: int
    ) -> list[AgentDecision]:
        result = await self._session.execute(
            select(AgentDecision)
            .where(AgentDecision.entity_id == entity_id)
            .order_by(AgentDecision.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_all(
        self, entity_id: str | None = None, limit: int = 100
    ) -> list[AgentDecision]:
        stmt = (
            select(AgentDecision).order_by(AgentDecision.created_at.desc()).limit(limit)
        )
        if entity_id is not None:
            stmt = stmt.where(AgentDecision.entity_id == entity_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()
