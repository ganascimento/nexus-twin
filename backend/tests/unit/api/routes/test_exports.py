from unittest.mock import MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport
from src.main import app


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
@patch("src.api.routes.exports.export_decision_history")
async def test_post_export_decisions_returns_202(mock_task, client):
    mock_result = MagicMock()
    mock_result.id = "task-exp-001"
    mock_task.delay.return_value = mock_result

    resp = await client.post("/api/v1/exports/decisions")

    assert resp.status_code == 202
    data = resp.json()
    assert data["task_id"] == "task-exp-001"


@pytest.mark.asyncio
@patch("src.api.routes.exports.export_decision_history")
async def test_post_export_decisions_with_filters(mock_task, client):
    mock_result = MagicMock()
    mock_result.id = "task-exp-002"
    mock_task.delay.return_value = mock_result

    resp = await client.post(
        "/api/v1/exports/decisions",
        json={"entity_id": "factory_01", "limit": 50},
    )

    assert resp.status_code == 202
    mock_task.delay.assert_called_once()


@pytest.mark.asyncio
@patch("src.api.routes.exports.export_event_history")
async def test_post_export_events_returns_202(mock_task, client):
    mock_result = MagicMock()
    mock_result.id = "task-exp-003"
    mock_task.delay.return_value = mock_result

    resp = await client.post("/api/v1/exports/events")

    assert resp.status_code == 202
    data = resp.json()
    assert data["task_id"] == "task-exp-003"


@pytest.mark.asyncio
@patch("src.api.routes.exports.export_world_snapshot")
async def test_post_export_world_snapshot_returns_202(mock_task, client):
    mock_result = MagicMock()
    mock_result.id = "task-exp-004"
    mock_task.delay.return_value = mock_result

    resp = await client.post("/api/v1/exports/world-snapshot")

    assert resp.status_code == 202
    data = resp.json()
    assert data["task_id"] == "task-exp-004"
