from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.event import EventRepository
from src.simulation.events import chaos_event
from src.simulation.publisher import publish_event

MANUAL_ONLY_EVENTS: frozenset[str] = frozenset(
    {"strike", "route_blocked", "storm", "sudden_demand_zero"}
)

AUTONOMOUS_COOLDOWN_TICKS = 24


async def inject_chaos_event(
    event_type: str,
    payload: dict,
    source: str,
    entity_type: str | None,
    entity_id: str | None,
    tick: int,
    session: AsyncSession,
    redis_client,
):
    if event_type in MANUAL_ONLY_EVENTS and source == "master_agent":
        raise ValueError(
            f"Event type '{event_type}' is manual-only and cannot be injected autonomously"
        )

    event = await EventRepository(session).create(
        {
            "status": "active",
            "tick_start": tick,
            "event_type": event_type,
            "payload": payload,
            "source": source,
            "entity_type": entity_type,
            "entity_id": entity_id,
        }
    )

    await publish_event(
        chaos_event(
            event_type=event_type,
            source=source,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            tick=tick,
        ),
        redis_client,
    )

    return event


async def resolve_chaos_event(event_id: str, tick: int, session: AsyncSession):
    return await EventRepository(session).resolve(event_id, tick)


async def can_inject_autonomous_event(current_tick: int, session: AsyncSession) -> bool:
    repo = EventRepository(session)

    active_count = await repo.count_active_autonomous()
    if active_count > 0:
        return False

    last_resolved_tick = await repo.get_last_resolved_autonomous_tick()
    if (
        last_resolved_tick is not None
        and current_tick - last_resolved_tick < AUTONOMOUS_COOLDOWN_TICKS
    ):
        return False

    return True
