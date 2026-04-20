from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.enums import WarehouseStatus
from src.simulation.engine import SimulationEngine
from src.world.entities.warehouse import Warehouse, WarehouseStock
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


def make_warehouse(**kwargs):
    defaults = dict(
        id="wh_01",
        name="Warehouse 1",
        lat=-22.8,
        lng=-45.8,
        region="interior",
        capacity_total=1000.0,
        status=WarehouseStatus.OPERATING,
        stocks={"cimento": WarehouseStock(stock=500.0, stock_reserved=0.0, min_stock=50.0)},
    )
    defaults.update(kwargs)
    return Warehouse(**defaults)


def make_orphaned_order(
    id=None,
    target_type="warehouse",
    target_id="wh_01",
    requester_type="store",
    requester_id="store_01",
    material_id="cimento",
    quantity_tons=20,
    age_ticks=5,
):
    order = MagicMock()
    order.id = id or uuid4()
    order.status = "confirmed"
    order.target_type = target_type
    order.target_id = target_id
    order.requester_type = requester_type
    order.requester_id = requester_id
    order.material_id = material_id
    order.quantity_tons = quantity_tons
    order.age_ticks = age_ticks
    return order


def make_idle_truck(id="truck_04", truck_type="terceiro", factory_id=None, lat=-23.5, lng=-46.6):
    truck = MagicMock()
    truck.id = id
    truck.status = "idle"
    truck.truck_type = truck_type
    truck.factory_id = factory_id
    truck.current_lat = lat
    truck.current_lng = lng
    return truck


def make_engine():
    redis_client = AsyncMock()
    mock_session = AsyncMock()

    @asynccontextmanager
    async def session_factory():
        yield mock_session

    engine = SimulationEngine(redis_client, session_factory)
    return engine


@pytest.mark.asyncio
async def test_retries_orphaned_order_with_idle_third_party():
    warehouse = make_warehouse()
    world_state = make_world_state(warehouses=[warehouse])
    order = make_orphaned_order()
    idle_truck = make_idle_truck()

    engine = make_engine()
    engine._tick = 10

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo, \
         patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []
        mock_event_repo.order_has_active_truck_event.return_value = False

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = []
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []
        mock_order_repo.get_confirmed_without_route.return_value = [order]

        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo
        mock_truck_repo.get_idle_by_factory.return_value = None
        mock_truck_repo.get_idle_third_party_for_load.return_value = idle_truck

        triggers = await engine._evaluate_triggers(world_state)

    event_calls = mock_event_repo.create.call_args_list
    retry_calls = [
        c for c in event_calls
        if c[0][0].get("event_type") == "contract_proposal"
    ]
    assert len(retry_calls) == 1
    assert retry_calls[0][0][0]["entity_id"] == "truck_04"
    assert retry_calls[0][0][0]["payload"]["order_id"] == str(order.id)


@pytest.mark.asyncio
async def test_retries_factory_order_with_proprietario():
    world_state = make_world_state()
    order = make_orphaned_order(target_type="factory", target_id="factory_01")
    prop_truck = make_idle_truck(id="truck_prop", truck_type="proprietario", factory_id="factory_01")

    engine = make_engine()
    engine._tick = 10

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo, \
         patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []
        mock_event_repo.order_has_active_truck_event.return_value = False

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = []
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []
        mock_order_repo.get_confirmed_without_route.return_value = [order]

        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo
        mock_truck_repo.get_idle_by_factory.return_value = prop_truck

        triggers = await engine._evaluate_triggers(world_state)

    event_calls = mock_event_repo.create.call_args_list
    retry_calls = [
        c for c in event_calls
        if c[0][0].get("event_type") == "new_order"
    ]
    assert len(retry_calls) == 1
    assert retry_calls[0][0][0]["entity_id"] == "truck_prop"


@pytest.mark.asyncio
async def test_skips_retry_when_no_truck_available():
    warehouse = make_warehouse()
    world_state = make_world_state(warehouses=[warehouse])
    order = make_orphaned_order()

    engine = make_engine()
    engine._tick = 10

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo, \
         patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []
        mock_event_repo.order_has_active_truck_event.return_value = False

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = []
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []
        mock_order_repo.get_confirmed_without_route.return_value = [order]

        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo
        mock_truck_repo.get_idle_by_factory.return_value = None
        mock_truck_repo.get_idle_third_party_for_load.return_value = None

        triggers = await engine._evaluate_triggers(world_state)

    event_calls = mock_event_repo.create.call_args_list
    retry_calls = [
        c for c in event_calls
        if c[0][0].get("event_type") in ("contract_proposal", "new_order")
    ]
    assert len(retry_calls) == 0


@pytest.mark.asyncio
async def test_limits_retry_to_10_per_tick():
    world_state = make_world_state()

    engine = make_engine()
    engine._tick = 10

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo, \
         patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []
        mock_event_repo.order_has_active_truck_event.return_value = False

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = []
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []
        mock_order_repo.get_confirmed_without_route.return_value = []

        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo

        await engine._evaluate_triggers(world_state)

    mock_order_repo.get_confirmed_without_route.assert_called_once_with(limit=10)


@pytest.mark.asyncio
async def test_no_duplicate_events_for_same_order():
    warehouse = make_warehouse()
    world_state = make_world_state(warehouses=[warehouse])
    order = make_orphaned_order()
    idle_truck = make_idle_truck()

    existing_event = MagicMock()
    existing_event.payload = {"order_id": str(order.id)}

    engine = make_engine()
    engine._tick = 10

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo, \
         patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.side_effect = lambda etype, eid: (
            [existing_event] if etype == "truck" and eid == "truck_04" else []
        )

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = []
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []
        mock_order_repo.get_confirmed_without_route.return_value = [order]

        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo
        mock_truck_repo.get_idle_by_factory.return_value = None
        mock_truck_repo.get_idle_third_party_for_load.return_value = idle_truck

        await engine._evaluate_triggers(world_state)

    event_calls = mock_event_repo.create.call_args_list
    retry_calls = [
        c for c in event_calls
        if c[0][0].get("event_type") in ("contract_proposal", "new_order")
    ]
    assert len(retry_calls) == 0
