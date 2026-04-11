import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.database.models import ChaosEvent
from src.services.chaos import ChaosService


def _make_event(**overrides) -> ChaosEvent:
    defaults = {
        "id": uuid.uuid4(),
        "event_type": "truck_breakdown",
        "source": "user",
        "entity_type": "truck",
        "entity_id": str(uuid.uuid4()),
        "payload": {"severity": "high"},
        "status": "active",
        "tick_start": 100,
        "tick_end": None,
    }
    defaults.update(overrides)
    event = MagicMock(spec=ChaosEvent)
    for k, v in defaults.items():
        setattr(event, k, v)
    return event


@pytest.fixture
def event_repo():
    repo = AsyncMock()
    repo.get_active = AsyncMock(return_value=[])
    repo.create = AsyncMock()
    repo.count_active_autonomous = AsyncMock(return_value=0)
    repo.get_last_resolved_autonomous_tick = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def session():
    s = AsyncMock()
    s.execute = AsyncMock()
    return s


@pytest.fixture
def service(event_repo, session):
    return ChaosService(event_repo, session)


# --- list_active_events ---


@pytest.mark.asyncio
async def test_list_active_events_delegates_to_repository(service, event_repo):
    events = [_make_event(), _make_event()]
    event_repo.get_active.return_value = events

    result = await service.list_active_events()

    event_repo.get_active.assert_awaited_once()
    assert result == events


# --- inject_event ---


@pytest.mark.asyncio
async def test_inject_event_creates_with_source_user(service, event_repo):
    data = {
        "event_type": "demand_spike",
        "entity_type": "store",
        "entity_id": str(uuid.uuid4()),
        "payload": {"multiplier": 3},
    }
    current_tick = 50
    created = _make_event(source="user", status="active", tick_start=50)
    event_repo.create.return_value = created

    result = await service.inject_event(data, current_tick)

    event_repo.create.assert_awaited_once()
    call_args = event_repo.create.call_args[0][0]
    assert call_args["source"] == "user"
    assert call_args["status"] == "active"
    assert call_args["tick_start"] == current_tick
    assert result == created


# --- inject_autonomous_event ---


@pytest.mark.asyncio
async def test_inject_autonomous_event_returns_none_when_active_event_exists(
    service, event_repo
):
    event_repo.count_active_autonomous.return_value = 1

    result = await service.inject_autonomous_event(
        {"event_type": "machine_failure", "payload": {}}, current_tick=100
    )

    assert result is None


@pytest.mark.asyncio
async def test_inject_autonomous_event_returns_none_when_cooldown_not_passed(
    service, event_repo
):
    event_repo.count_active_autonomous.return_value = 0
    event_repo.get_last_resolved_autonomous_tick.return_value = 90

    result = await service.inject_autonomous_event(
        {"event_type": "machine_failure", "payload": {}}, current_tick=100
    )

    assert result is None


@pytest.mark.asyncio
async def test_inject_autonomous_event_creates_when_conditions_met(
    service, event_repo
):
    event_repo.count_active_autonomous.return_value = 0
    event_repo.get_last_resolved_autonomous_tick.return_value = 50

    created = _make_event(source="master_agent")
    event_repo.create.return_value = created

    result = await service.inject_autonomous_event(
        {"event_type": "machine_failure", "payload": {}}, current_tick=100
    )

    assert result == created
    call_args = event_repo.create.call_args[0][0]
    assert call_args["source"] == "master_agent"


@pytest.mark.asyncio
async def test_inject_autonomous_event_creates_when_no_prior_resolved(
    service, event_repo
):
    event_repo.count_active_autonomous.return_value = 0
    event_repo.get_last_resolved_autonomous_tick.return_value = None

    created = _make_event(source="master_agent")
    event_repo.create.return_value = created

    result = await service.inject_autonomous_event(
        {"event_type": "machine_failure", "payload": {}}, current_tick=100
    )

    assert result == created


# --- resolve_event ---


@pytest.mark.asyncio
async def test_resolve_event_updates_status_and_tick_end(service, event_repo):
    event_id = uuid.uuid4()
    active_event = _make_event(id=event_id, status="active")
    resolved_event = _make_event(id=event_id, status="resolved", tick_end=120)

    event_repo.get_by_id = AsyncMock(return_value=active_event)
    event_repo.resolve.return_value = resolved_event

    result = await service.resolve_event(event_id, current_tick=120)

    event_repo.resolve.assert_awaited_once_with(event_id, 120)
    assert result.status == "resolved"
    assert result.tick_end == 120


@pytest.mark.asyncio
async def test_resolve_event_raises_for_nonexistent_event(service, event_repo):
    event_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(Exception):
        await service.resolve_event(uuid.uuid4(), current_tick=120)


@pytest.mark.asyncio
async def test_resolve_event_raises_for_already_resolved_event(service, event_repo):
    resolved = _make_event(status="resolved", tick_end=100)
    event_repo.get_by_id = AsyncMock(return_value=resolved)

    with pytest.raises(Exception):
        await service.resolve_event(resolved.id, current_tick=120)


# --- can_inject_autonomous_event ---


@pytest.mark.asyncio
async def test_can_inject_autonomous_event_returns_true_when_allowed(
    service, event_repo
):
    event_repo.count_active_autonomous.return_value = 0
    event_repo.get_last_resolved_autonomous_tick.return_value = 50

    result = await service.can_inject_autonomous_event(current_tick=100)

    assert result is True


@pytest.mark.asyncio
async def test_can_inject_autonomous_event_returns_false_when_active_event(
    service, event_repo
):
    event_repo.count_active_autonomous.return_value = 1

    result = await service.can_inject_autonomous_event(current_tick=100)

    assert result is False


@pytest.mark.asyncio
async def test_can_inject_autonomous_event_returns_false_when_cooldown_active(
    service, event_repo
):
    event_repo.count_active_autonomous.return_value = 0
    event_repo.get_last_resolved_autonomous_tick.return_value = 90

    result = await service.can_inject_autonomous_event(current_tick=100)

    assert result is False
