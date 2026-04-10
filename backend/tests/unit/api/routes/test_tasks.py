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
@patch("src.api.routes.tasks.AsyncResult")
async def test_task_status_pending(mock_async_result, client):
    mock_result = MagicMock()
    mock_result.status = "PENDING"
    mock_result.result = None
    mock_async_result.return_value = mock_result

    resp = await client.get("/api/v1/tasks/task-123/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == "task-123"
    assert data["status"] == "PENDING"
    assert data["result"] is None
    assert data["error"] is None


@pytest.mark.asyncio
@patch("src.api.routes.tasks.AsyncResult")
async def test_task_status_success_includes_result(mock_async_result, client):
    mock_result = MagicMock()
    mock_result.status = "SUCCESS"
    mock_result.result = {"orders_delivered": 5, "orders_late": 1}
    mock_async_result.return_value = mock_result

    resp = await client.get("/api/v1/tasks/task-456/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == "task-456"
    assert data["status"] == "SUCCESS"
    assert data["result"] == {"orders_delivered": 5, "orders_late": 1}
    assert data["error"] is None


@pytest.mark.asyncio
@patch("src.api.routes.tasks.AsyncResult")
async def test_task_status_failure_includes_error(mock_async_result, client):
    mock_result = MagicMock()
    mock_result.status = "FAILURE"
    mock_result.result = Exception("DB connection failed")
    mock_async_result.return_value = mock_result

    resp = await client.get("/api/v1/tasks/task-789/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == "task-789"
    assert data["status"] == "FAILURE"
    assert data["error"] == "DB connection failed"
    assert data["result"] is None
