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
@patch("src.api.routes.reports.generate_efficiency_report")
async def test_post_efficiency_report_returns_202(mock_task, client):
    mock_result = MagicMock()
    mock_result.id = "task-abc-123"
    mock_task.delay.return_value = mock_result

    resp = await client.post("/api/v1/reports/efficiency")

    assert resp.status_code == 202
    data = resp.json()
    assert data["task_id"] == "task-abc-123"
    mock_task.delay.assert_called_once()


@pytest.mark.asyncio
@patch("src.api.routes.reports.generate_decision_summary")
async def test_post_decision_summary_returns_202(mock_task, client):
    mock_result = MagicMock()
    mock_result.id = "task-def-456"
    mock_task.delay.return_value = mock_result

    resp = await client.post("/api/v1/reports/decisions")

    assert resp.status_code == 202
    data = resp.json()
    assert data["task_id"] == "task-def-456"


@pytest.mark.asyncio
@patch("src.api.routes.reports.generate_decision_summary")
async def test_post_decision_summary_with_custom_ticks(mock_task, client):
    mock_result = MagicMock()
    mock_result.id = "task-ghi-789"
    mock_task.delay.return_value = mock_result

    resp = await client.post("/api/v1/reports/decisions", json={"ticks": 48})

    assert resp.status_code == 202
    mock_task.delay.assert_called_once()
