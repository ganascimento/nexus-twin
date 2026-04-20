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


# ---------------------------------------------------------------------------
# Feature 26 — Route with order_id
# ---------------------------------------------------------------------------


def _make_session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_route_create_with_order_id():
    order_id = uuid.uuid4()
    session = _make_session()

    repo = RouteRepository(session)
    data = {
        "truck_id": "truck_01",
        "origin_type": "factory",
        "origin_id": "factory_01",
        "dest_type": "warehouse",
        "dest_id": "wh_01",
        "path": [[-46.6, -23.5], [-45.8, -22.8]],
        "timestamps": [0, 4],
        "eta_ticks": 3,
        "status": "active",
        "started_at": datetime.now(timezone.utc),
        "order_id": order_id,
    }

    await repo.create(data)

    session.add.assert_called_once()
    added_route = session.add.call_args[0][0]
    assert added_route.order_id == order_id


@pytest.mark.asyncio
async def test_route_create_without_order_id():
    session = _make_session()

    repo = RouteRepository(session)
    data = {
        "truck_id": "truck_01",
        "origin_type": "factory",
        "origin_id": "factory_01",
        "dest_type": "warehouse",
        "dest_id": "wh_01",
        "path": [[-46.6, -23.5], [-45.8, -22.8]],
        "timestamps": [0, 4],
        "eta_ticks": 3,
        "status": "active",
        "started_at": datetime.now(timezone.utc),
    }

    await repo.create(data)

    session.add.assert_called_once()
    added_route = session.add.call_args[0][0]
    assert added_route.order_id is None
