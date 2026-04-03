from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ChaosEvent


class EventRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, data: dict) -> ChaosEvent:
        event = ChaosEvent(**data)
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(event)
        return event

    async def get_active(self) -> list[ChaosEvent]:
        result = await self._session.execute(
            select(ChaosEvent).where(ChaosEvent.status == "active")
        )
        return result.scalars().all()

    async def resolve(self, event_id: UUID, tick_end: int) -> ChaosEvent:
        await self._session.execute(
            update(ChaosEvent)
            .where(ChaosEvent.id == event_id)
            .values(status="resolved", tick_end=tick_end)
        )
        result = await self._session.execute(
            select(ChaosEvent).where(ChaosEvent.id == event_id)
        )
        return result.scalar_one()

    async def count_active(self) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(ChaosEvent)
            .where(ChaosEvent.status == "active")
        )
        return int(result.scalar())

    async def get_last_resolved_autonomous_tick(self) -> int | None:
        result = await self._session.execute(
            select(ChaosEvent.tick_end)
            .where(ChaosEvent.source == "master_agent", ChaosEvent.status == "resolved")
            .order_by(ChaosEvent.tick_end.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
