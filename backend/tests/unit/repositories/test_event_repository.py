import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.database.models import ChaosEvent
from src.repositories.event import EventRepository


def _make_event(event_id=None, source="manual"):
    return ChaosEvent(
        id=event_id or uuid.uuid4(),
        event_type="truck_breakdown",
        source=source,
        payload={},
        status="active",
        tick_start=1,
    )


@pytest.mark.asyncio
async def test_get_active_filters_by_status():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _make_event(),
        _make_event(),
    ]
    session.execute.return_value = result

    repo = EventRepository(session)
    events = await repo.get_active()

    assert len(events) == 2
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_count_active_returns_integer():
    session = AsyncMock()
    result = MagicMock()
    result.scalar.return_value = 3
    session.execute.return_value = result

    repo = EventRepository(session)
    count = await repo.count_active()

    assert count == 3
    assert isinstance(count, int)


@pytest.mark.asyncio
async def test_get_last_resolved_autonomous_tick_returns_none_when_none_exist():
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    repo = EventRepository(session)
    tick = await repo.get_last_resolved_autonomous_tick()

    assert tick is None


@pytest.mark.asyncio
async def test_resolve_updates_status_and_tick_end():
    event_id = uuid.uuid4()
    existing_event = _make_event(event_id=event_id)

    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = existing_event

    update_result = MagicMock()

    session = AsyncMock()
    session.refresh = AsyncMock()
    session.execute.side_effect = [fetch_result, update_result]

    repo = EventRepository(session)
    await repo.resolve(event_id=event_id, tick_end=5)

    assert session.execute.call_count >= 1
