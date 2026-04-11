from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ChaosEvent
from src.repositories.event import EventRepository
from src.services import ConflictError, NotFoundError

AUTONOMOUS_COOLDOWN_TICKS = 24


class ChaosService:
    def __init__(self, event_repo: EventRepository, session: AsyncSession):
        self._repo = event_repo
        self._session = session

    async def list_active_events(self) -> list[ChaosEvent]:
        return await self._repo.get_active()

    async def inject_event(self, data: dict, current_tick: int) -> ChaosEvent:
        return await self._repo.create(
            {**data, "source": "user", "status": "active", "tick_start": current_tick}
        )

    async def inject_autonomous_event(
        self, data: dict, current_tick: int
    ) -> ChaosEvent | None:
        if not await self.can_inject_autonomous_event(current_tick):
            return None

        return await self._repo.create(
            {**data, "source": "master_agent", "status": "active", "tick_start": current_tick}
        )

    async def resolve_event(self, event_id: UUID, current_tick: int) -> ChaosEvent:
        event = await self._repo.get_by_id(event_id)
        if event is None:
            raise NotFoundError(f"ChaosEvent '{event_id}' not found")
        if event.status == "resolved":
            raise ConflictError(f"Event {event_id} is already resolved")
        return await self._repo.resolve(event_id, current_tick)

    async def can_inject_autonomous_event(self, current_tick: int) -> bool:
        active_count = await self._repo.count_active_autonomous()
        if active_count > 0:
            return False
        last_tick = await self._repo.get_last_resolved_autonomous_tick()
        if last_tick is not None and (current_tick - last_tick) < AUTONOMOUS_COOLDOWN_TICKS:
            return False
        return True
