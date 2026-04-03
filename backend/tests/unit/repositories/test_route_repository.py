import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.repositories.route import RouteRepository


@pytest.mark.asyncio
async def test_get_active_by_truck_returns_none_when_no_active_route():
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    repo = RouteRepository(session)
    route = await repo.get_active_by_truck("t1")

    assert route is None


@pytest.mark.asyncio
async def test_update_status_sets_completed_at_when_completed():
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 1
    session.execute.return_value = result

    repo = RouteRepository(session)
    route_id = uuid.uuid4()
    completed_at = datetime.now(timezone.utc)

    await repo.update_status(
        route_id=route_id, status="completed", completed_at=completed_at
    )

    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_update_status_does_not_set_completed_at_when_interrupted():
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 1
    session.execute.return_value = result

    repo = RouteRepository(session)
    route_id = uuid.uuid4()

    await repo.update_status(route_id=route_id, status="interrupted")

    session.execute.assert_called_once()
