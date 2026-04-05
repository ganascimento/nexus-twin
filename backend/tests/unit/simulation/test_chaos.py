from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.simulation.chaos import (
    can_inject_autonomous_event,
    inject_chaos_event,
    resolve_chaos_event,
)


@pytest.fixture
def session():
    return AsyncMock()


@pytest.fixture
def redis_client():
    return AsyncMock()


def make_mock_event(status="active", tick_end=None, source="master_agent"):
    event = MagicMock()
    event.status = status
    event.tick_end = tick_end
    event.source = source
    return event


@pytest.mark.asyncio
async def test_inject_chaos_event_persists_event_with_active_status(
    session, redis_client
):
    mock_event = make_mock_event(status="active")

    with patch("src.simulation.chaos.EventRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo
        mock_repo.create.return_value = mock_event

        with patch("src.simulation.chaos.publish_event", new_callable=AsyncMock):
            result = await inject_chaos_event(
                event_type="machine_breakdown",
                payload={"machine": "press-1"},
                source="master_agent",
                entity_type="factory",
                entity_id="f-001",
                tick=5,
                session=session,
                redis_client=redis_client,
            )

    create_data = mock_repo.create.call_args[0][0]
    assert create_data["status"] == "active"
    assert create_data["tick_start"] == 5
    assert result == mock_event


@pytest.mark.asyncio
async def test_manual_only_events_rejected_when_source_is_master_agent(
    session, redis_client
):
    with patch("src.simulation.chaos.EventRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo

        with pytest.raises(ValueError, match="manual"):
            await inject_chaos_event(
                event_type="strike",
                payload={},
                source="master_agent",
                entity_type=None,
                entity_id=None,
                tick=1,
                session=session,
                redis_client=redis_client,
            )

    mock_repo.create.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", ["route_blocked", "storm", "sudden_demand_zero"])
async def test_manual_only_events_rejected_for_route_blocked(
    event_type, session, redis_client
):
    with patch("src.simulation.chaos.EventRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo

        with pytest.raises(ValueError):
            await inject_chaos_event(
                event_type=event_type,
                payload={},
                source="master_agent",
                entity_type=None,
                entity_id=None,
                tick=1,
                session=session,
                redis_client=redis_client,
            )

    mock_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_can_inject_autonomous_blocked_when_active_event_exists(session):
    with patch("src.simulation.chaos.EventRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo
        mock_repo.count_active_autonomous.return_value = 1

        result = await can_inject_autonomous_event(current_tick=50, session=session)

    assert result is False


@pytest.mark.asyncio
async def test_can_inject_autonomous_blocked_during_cooldown(session):
    with patch("src.simulation.chaos.EventRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo
        mock_repo.count_active_autonomous.return_value = 0
        # Last autonomous event resolved at tick 40; current tick 50 → cooldown of 10 < 24
        mock_repo.get_last_resolved_autonomous_tick.return_value = 40

        result = await can_inject_autonomous_event(current_tick=50, session=session)

    assert result is False


@pytest.mark.asyncio
async def test_can_inject_autonomous_allowed_after_cooldown(session):
    with patch("src.simulation.chaos.EventRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo
        mock_repo.count_active_autonomous.return_value = 0
        # Last autonomous event resolved at tick 10; current tick 50 → cooldown of 40 >= 24
        mock_repo.get_last_resolved_autonomous_tick.return_value = 10

        result = await can_inject_autonomous_event(current_tick=50, session=session)

    assert result is True


@pytest.mark.asyncio
async def test_resolve_chaos_event_sets_resolved_status(session):
    resolved_event = make_mock_event(status="resolved", tick_end=42)

    with patch("src.simulation.chaos.EventRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo
        mock_repo.resolve.return_value = resolved_event

        result = await resolve_chaos_event(event_id="evt-001", tick=42, session=session)

    mock_repo.resolve.assert_called_once()
    call_args = mock_repo.resolve.call_args
    assert call_args[0][1] == 42 or call_args[1].get("tick_end") == 42
    assert result.status == "resolved"
    assert result.tick_end == 42
