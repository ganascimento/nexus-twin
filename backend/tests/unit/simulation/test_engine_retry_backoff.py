from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.enums import StoreStatus
from src.simulation.engine import SimulationEngine
from src.world.entities.store import Store, StoreStock
from src.world.state import WorldState


def make_world_state(**kwargs):
    defaults = dict(
        tick=1,
        simulated_timestamp=datetime(2024, 1, 1),
        materials=[],
        factories=[],
        warehouses=[],
        stores=[],
        trucks=[],
    )
    defaults.update(kwargs)
    return WorldState(**defaults)


def make_store(**kwargs):
    defaults = dict(
        id="store_01",
        name="Store 1",
        lat=-23.5,
        lng=-46.6,
        status=StoreStatus.OPEN,
        stocks={"cimento": StoreStock(stock=50.0, demand_rate=1.0, reorder_point=5.0)},
    )
    defaults.update(kwargs)
    return Store(**defaults)


def make_rejected_order(
    id=None,
    requester_id="store_01",
    target_id="wh_01",
    material_id="cimento",
    retry_after_tick=6,
    age_ticks=8,
):
    order = MagicMock()
    order.id = id or uuid4()
    order.status = "rejected"
    order.requester_id = requester_id
    order.target_id = target_id
    order.material_id = material_id
    order.quantity_tons = 20
    order.retry_after_tick = retry_after_tick
    order.age_ticks = age_ticks
    return order


def make_engine():
    redis_client = AsyncMock()
    mock_session = AsyncMock()

    @asynccontextmanager
    async def session_factory():
        yield mock_session

    engine = SimulationEngine(redis_client, session_factory)
    return engine


@pytest.mark.asyncio
async def test_fires_retry_eligible_for_store():
    store = make_store()
    world_state = make_world_state(stores=[store])
    order = make_rejected_order(retry_after_tick=6, age_ticks=8)

    engine = make_engine()
    engine._tick = 10

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo, \
         patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = []
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []
        mock_order_repo.get_confirmed_without_route.return_value = []
        mock_order_repo.get_retry_eligible.return_value = [order]

        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo

        triggers = await engine._evaluate_triggers(world_state)

    retry_triggers = [
        t for t in triggers if t[1].event_type == "order_retry_eligible"
    ]
    assert len(retry_triggers) == 1
    assert retry_triggers[0][1].entity_id == "store_01"


@pytest.mark.asyncio
async def test_no_retry_if_backoff_active():
    store = make_store()
    world_state = make_world_state(stores=[store])

    engine = make_engine()
    engine._tick = 5

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo, \
         patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = []
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []
        mock_order_repo.get_confirmed_without_route.return_value = []
        mock_order_repo.get_retry_eligible.return_value = []

        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo

        triggers = await engine._evaluate_triggers(world_state)

    retry_triggers = [
        t for t in triggers if t[1].event_type == "order_retry_eligible"
    ]
    assert len(retry_triggers) == 0


@pytest.mark.asyncio
async def test_retry_trigger_includes_order_data():
    store = make_store()
    world_state = make_world_state(stores=[store])
    order_id = uuid4()
    order = make_rejected_order(id=order_id, target_id="wh_01", material_id="cimento")

    engine = make_engine()
    engine._tick = 10

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo, \
         patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = []
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []
        mock_order_repo.get_confirmed_without_route.return_value = []
        mock_order_repo.get_retry_eligible.return_value = [order]

        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo

        triggers = await engine._evaluate_triggers(world_state)

    retry_trigger = [
        t for t in triggers if t[1].event_type == "order_retry_eligible"
    ][0]
    payload = retry_trigger[1].payload
    assert payload["order_id"] == str(order_id)
    assert payload["material_id"] == "cimento"
    assert payload["original_target_id"] == "wh_01"
