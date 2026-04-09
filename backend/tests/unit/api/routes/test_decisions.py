import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport

from src.main import app
from src.api.dependencies import get_agent_decision_repo


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
async def client(mock_repo):
    app.dependency_overrides[get_agent_decision_repo] = lambda: mock_repo
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _make_decision(
    decision_id=None,
    entity_id="warehouse_01",
    agent_type="warehouse",
    action="request_resupply",
    event_type="low_stock",
    payload=None,
    tick=10,
    reasoning=None,
):
    d = MagicMock()
    d.id = decision_id or uuid.uuid4()
    d.entity_id = entity_id
    d.agent_type = agent_type
    d.action = action
    d.event_type = event_type
    d.payload = payload or {"quantity_tons": 50, "from_factory": "factory_01"}
    d.tick = tick
    d.reasoning = reasoning
    d.created_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    return d


@pytest.mark.asyncio
async def test_list_decisions(client, mock_repo):
    decisions = [
        _make_decision(),
        _make_decision(entity_id="store_01", agent_type="store", action="order_replenishment"),
    ]
    mock_repo.get_all.return_value = decisions

    resp = await client.get("/api/v1/decisions/")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    mock_repo.get_all.assert_called_once()


@pytest.mark.asyncio
async def test_list_decisions_with_filters(client, mock_repo):
    decisions = [_make_decision(entity_id="factory_01", agent_type="factory")]
    mock_repo.get_all.return_value = decisions

    resp = await client.get("/api/v1/decisions/", params={"entity_id": "factory_01", "limit": 10})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    mock_repo.get_all.assert_called_once_with(entity_id="factory_01", limit=10)


@pytest.mark.asyncio
async def test_get_decisions_for_entity(client, mock_repo):
    decisions = [
        _make_decision(entity_id="warehouse_01", tick=10),
        _make_decision(entity_id="warehouse_01", tick=8),
    ]
    mock_repo.get_recent_by_entity.return_value = decisions

    resp = await client.get("/api/v1/decisions/warehouse_01")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    mock_repo.get_recent_by_entity.assert_called_once()


@pytest.mark.asyncio
async def test_get_decisions_for_nonexistent_entity(client, mock_repo):
    mock_repo.get_recent_by_entity.return_value = []

    resp = await client.get("/api/v1/decisions/nonexistent_entity")

    assert resp.status_code == 404
