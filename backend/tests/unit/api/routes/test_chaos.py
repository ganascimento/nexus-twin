import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport

from src.main import app
from src.api.dependencies import get_chaos_service
from src.services import NotFoundError, ConflictError


@pytest.fixture
def mock_service():
    return AsyncMock()


@pytest.fixture
async def client(mock_service):
    app.dependency_overrides[get_chaos_service] = lambda: mock_service
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _make_event(
    event_id=None,
    event_type="route_blocked",
    source="user",
    entity_type="truck",
    entity_id="truck_01",
    payload=None,
    status="active",
    tick_start=10,
    tick_end=None,
):
    e = MagicMock()
    e.id = event_id or uuid.uuid4()
    e.event_type = event_type
    e.source = source
    e.entity_type = entity_type
    e.entity_id = entity_id
    e.payload = payload or {"highway": "SP-330"}
    e.status = status
    e.tick_start = tick_start
    e.tick_end = tick_end
    e.created_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    return e


@pytest.mark.asyncio
async def test_list_active_events(client, mock_service):
    events = [_make_event(), _make_event(event_type="truck_breakdown")]
    mock_service.list_active_events.return_value = events

    resp = await client.get("/api/v1/chaos/events")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    mock_service.list_active_events.assert_called_once()


@pytest.mark.asyncio
async def test_inject_event(client, mock_service):
    created = _make_event()
    mock_service.inject_event.return_value = created

    body = {
        "event_type": "route_blocked",
        "entity_type": "truck",
        "entity_id": "truck_01",
        "payload": {"highway": "SP-330"},
    }
    resp = await client.post("/api/v1/chaos/events", json=body, params={"current_tick": 10})

    assert resp.status_code == 201
    mock_service.inject_event.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_event(client, mock_service):
    event_id = uuid.uuid4()
    resolved = _make_event(event_id=event_id, status="resolved", tick_end=20)
    mock_service.resolve_event.return_value = resolved

    resp = await client.post(f"/api/v1/chaos/events/{event_id}/resolve", params={"current_tick": 20})

    assert resp.status_code == 200
    mock_service.resolve_event.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_event_not_found(client, mock_service):
    event_id = uuid.uuid4()
    mock_service.resolve_event.side_effect = NotFoundError(f"Event {event_id} not found")

    resp = await client.post(f"/api/v1/chaos/events/{event_id}/resolve", params={"current_tick": 10})

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_resolve_event_already_resolved(client, mock_service):
    event_id = uuid.uuid4()
    mock_service.resolve_event.side_effect = ConflictError(
        f"Event {event_id} is already resolved"
    )

    resp = await client.post(f"/api/v1/chaos/events/{event_id}/resolve", params={"current_tick": 10})

    assert resp.status_code == 409
