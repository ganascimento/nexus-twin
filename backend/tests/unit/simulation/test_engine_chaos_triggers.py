from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.enums import FactoryStatus, WarehouseStatus, StoreStatus
from src.simulation.engine import SimulationEngine
from src.world.entities.factory import Factory, FactoryProduct
from src.world.entities.store import Store, StoreStock
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


def make_factory(**kwargs):
    defaults = dict(
        id="factory_01",
        name="Factory 1",
        lat=-22.9,
        lng=-47.1,
        status=FactoryStatus.OPERATING,
        products={"cimento": FactoryProduct(
            stock=100.0, stock_reserved=0.0, stock_max=200.0,
            production_rate_max=10.0, production_rate_current=5.0,
        )},
        partner_warehouses=[],
    )
    defaults.update(kwargs)
    return Factory(**defaults)


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


def make_engine():
    redis_client = AsyncMock()
    mock_session = AsyncMock()

    @asynccontextmanager
    async def session_factory():
        yield mock_session

    engine = SimulationEngine(redis_client, session_factory)
    return engine


def make_chaos_event(event_type, entity_type, entity_id, payload=None):
    evt = MagicMock()
    evt.id = uuid4()
    evt.event_type = event_type
    evt.entity_type = entity_type
    evt.entity_id = entity_id
    evt.payload = payload or {}
    evt.status = "active"
    return evt


@pytest.mark.asyncio
async def test_fires_trigger_for_factory_machine_breakdown():
    factory = make_factory()
    world_state = make_world_state(factories=[factory])
    chaos_evt = make_chaos_event("machine_breakdown", "factory", "factory_01")

    engine = make_engine()
    engine._tick = 5

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo, \
         patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo

        def side_effect(etype, eid):
            if etype == "factory" and eid == "factory_01":
                return [chaos_evt]
            return []

        mock_event_repo.get_active_for_entity.side_effect = side_effect

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = []
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []
        mock_order_repo.get_confirmed_without_route.return_value = []
        mock_order_repo.get_retry_eligible.return_value = []

        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo

        triggers = await engine._evaluate_triggers(world_state)

    factory_triggers = [
        t for t in triggers
        if t[1].entity_id == "factory_01" and t[1].event_type == "machine_breakdown"
    ]
    assert len(factory_triggers) == 1


@pytest.mark.asyncio
async def test_fires_trigger_for_store_demand_spike():
    store = make_store()
    world_state = make_world_state(stores=[store])
    chaos_evt = make_chaos_event("demand_spike", "store", "store_01")

    engine = make_engine()
    engine._tick = 5

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo, \
         patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo

        def side_effect(etype, eid):
            if etype == "store" and eid == "store_01":
                return [chaos_evt]
            return []

        mock_event_repo.get_active_for_entity.side_effect = side_effect

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = []
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []
        mock_order_repo.get_confirmed_without_route.return_value = []
        mock_order_repo.get_retry_eligible.return_value = []

        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo

        triggers = await engine._evaluate_triggers(world_state)

    store_triggers = [
        t for t in triggers
        if t[1].entity_id == "store_01" and t[1].event_type == "demand_spike"
    ]
    assert len(store_triggers) == 1


@pytest.mark.asyncio
async def test_resolves_event_after_trigger():
    factory = make_factory()
    world_state = make_world_state(factories=[factory])
    chaos_evt = make_chaos_event("machine_breakdown", "factory", "factory_01")

    engine = make_engine()
    engine._tick = 5

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo, \
         patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo

        def side_effect(etype, eid):
            if etype == "factory" and eid == "factory_01":
                return [chaos_evt]
            return []

        mock_event_repo.get_active_for_entity.side_effect = side_effect

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = []
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []
        mock_order_repo.get_confirmed_without_route.return_value = []
        mock_order_repo.get_retry_eligible.return_value = []

        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo

        await engine._evaluate_triggers(world_state)

    mock_event_repo.resolve.assert_any_call(chaos_evt.id, 5)


@pytest.mark.asyncio
async def test_does_not_retrigger_resolved():
    factory = make_factory()
    world_state = make_world_state(factories=[factory])

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

    factory_chaos = [
        t for t in triggers
        if t[1].entity_id == "factory_01" and t[1].event_type == "machine_breakdown"
    ]
    assert len(factory_chaos) == 0
