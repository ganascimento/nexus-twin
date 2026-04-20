import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.enums import (
    FactoryStatus,
    RouteNodeType,
    StoreStatus,
    TruckStatus,
    TruckType,
    WarehouseStatus,
)
from src.simulation.engine import SimulationEngine
from src.world.entities.factory import Factory, FactoryProduct
from src.world.entities.store import Store, StoreStock
from src.world.entities.truck import Truck, TruckCargo, TruckRoute
from src.world.entities.warehouse import Warehouse
from src.world.state import WorldState

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


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


def make_truck(**kwargs):
    defaults = dict(
        id="truck-001",
        truck_type=TruckType.PROPRIETARIO,
        capacity_tons=20.0,
        base_lat=-23.5,
        base_lng=-46.6,
        current_lat=-23.5,
        current_lng=-46.6,
        degradation=0.0,
        breakdown_risk=0.0,
        status=TruckStatus.IDLE,
    )
    defaults.update(kwargs)
    return Truck(**defaults)


def make_store(stocks: dict | None = None, **kwargs) -> Store:
    defaults = dict(
        id="store-001",
        name="Store 1",
        lat=-23.5,
        lng=-46.6,
        status=StoreStatus.OPEN,
        stocks=stocks or {},
    )
    defaults.update(kwargs)
    return Store(**defaults)


def make_warehouse(stocks: dict | None = None, **kwargs) -> Warehouse:
    defaults = dict(
        id="wh-001",
        name="Warehouse 1",
        lat=-22.8,
        lng=-45.8,
        region="interior",
        capacity_total=1000.0,
        status=WarehouseStatus.OPERATING,
        stocks=stocks or {},
    )
    defaults.update(kwargs)
    return Warehouse(**defaults)


def _make_mock_session():
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.begin_nested = AsyncMock()
    session.close = AsyncMock()
    session.get = AsyncMock()
    return session


def make_engine(redis_client=None, session_factory=None, max_workers=4):
    rc = redis_client or AsyncMock()

    if session_factory is None:
        mock_session = _make_mock_session()

        @asynccontextmanager
        async def _session_factory():
            yield mock_session

        session_factory = _session_factory

    engine = SimulationEngine(rc, session_factory)
    engine._semaphore = asyncio.Semaphore(max_workers)
    return engine


# ---------------------------------------------------------------------------
# _apply_physics — truck position
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_physics_advances_truck_position():
    truck = make_truck(
        status=TruckStatus.IN_TRANSIT,
        cargo=TruckCargo(
            material_id="mat-001",
            quantity_tons=10.0,
            origin_type=RouteNodeType.FACTORY,
            origin_id="f-001",
            destination_type=RouteNodeType.WAREHOUSE,
            destination_id="w-001",
        ),
    )
    world_state = make_world_state(trucks=[truck])

    mock_route = MagicMock()
    mock_route.id = "route-001"
    mock_route.eta_ticks = 3
    mock_route.path = [[-46.6, -23.5], [-45.8, -22.8]]
    mock_route.timestamps = [0, 4]

    with patch("src.simulation.engine.TruckRepository") as MockTruckRepo, \
         patch("src.simulation.engine.RouteRepository") as MockRouteRepo:
        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo
        mock_route_repo = AsyncMock()
        mock_route_repo.get_active_by_truck.return_value = mock_route
        MockRouteRepo.return_value = mock_route_repo

        engine = make_engine()
        engine._tick = 2
        await engine._apply_physics(world_state)

    mock_truck_repo.update_position.assert_called_once()
    call_args = mock_truck_repo.update_position.call_args[0]
    truck_id, new_lat, new_lng = call_args
    assert truck_id == "truck-001"
    assert new_lat == pytest.approx(-23.15, abs=1e-6)
    assert new_lng == pytest.approx(-46.2, abs=1e-6)


@pytest.mark.asyncio
async def test_apply_physics_marks_truck_arrived_when_route_complete():
    truck = make_truck(
        status=TruckStatus.IN_TRANSIT,
        cargo=TruckCargo(
            material_id="mat-001",
            quantity_tons=10.0,
            origin_type=RouteNodeType.FACTORY,
            origin_id="f-001",
            destination_type=RouteNodeType.WAREHOUSE,
            destination_id="w-001",
        ),
    )
    world_state = make_world_state(trucks=[truck])

    mock_route = MagicMock()
    mock_route.id = "route-001"
    mock_route.eta_ticks = 1
    mock_route.path = [[-46.6, -23.5], [-45.8, -22.8]]
    mock_route.timestamps = [0, 2]

    with patch("src.simulation.engine.TruckRepository") as MockTruckRepo, \
         patch("src.simulation.engine.RouteRepository") as MockRouteRepo:
        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo
        mock_route_repo = AsyncMock()
        mock_route_repo.get_active_by_truck.return_value = mock_route
        MockRouteRepo.return_value = mock_route_repo

        engine = make_engine()
        engine._tick = 2
        await engine._apply_physics(world_state)

    mock_truck_repo.update_status.assert_called_once_with("truck-001", "idle")
    mock_truck_repo.set_cargo.assert_called_once_with("truck-001", None)
    mock_truck_repo.set_active_route.assert_called_once_with("truck-001", None)


# ---------------------------------------------------------------------------
# _apply_physics — store stock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_physics_decrements_store_stock_by_demand_rate():
    store = make_store(
        stocks={"mat-001": StoreStock(stock=10.0, demand_rate=3.0, reorder_point=2.0)}
    )
    world_state = make_world_state(stores=[store])

    with patch("src.simulation.engine.StoreRepository") as MockStoreRepo:
        mock_store_repo = AsyncMock()
        MockStoreRepo.return_value = mock_store_repo

        engine = make_engine()
        engine._tick = 1
        await engine._apply_physics(world_state)

    # Stock goes from 10.0 to 7.0 (delta = -3.0)
    mock_store_repo.update_stock.assert_called_once_with(
        "store-001", "mat-001", pytest.approx(-3.0)
    )


@pytest.mark.asyncio
async def test_apply_physics_store_stock_does_not_go_below_zero():
    store = make_store(
        stocks={"mat-001": StoreStock(stock=1.0, demand_rate=5.0, reorder_point=0.0)}
    )
    world_state = make_world_state(stores=[store])

    with patch("src.simulation.engine.StoreRepository") as MockStoreRepo:
        mock_store_repo = AsyncMock()
        MockStoreRepo.return_value = mock_store_repo

        engine = make_engine()
        engine._tick = 1
        await engine._apply_physics(world_state)

    call_args = mock_store_repo.update_stock.call_args[0]
    _, _, delta = call_args
    # stock + delta must not be negative: 1.0 + delta >= 0 → delta >= -1.0
    assert delta == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# _apply_physics — factory production
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_physics_increments_factory_stock_by_production_rate():
    factory = Factory(
        id="f-001",
        name="Factory 1",
        lat=-22.9,
        lng=-47.1,
        status=FactoryStatus.OPERATING,
        products={
            "mat-001": FactoryProduct(
                stock=50.0,
                stock_reserved=0.0,
                stock_max=200.0,
                production_rate_max=10.0,
                production_rate_current=10.0,
            )
        },
        partner_warehouses=[],
    )
    world_state = make_world_state(factories=[factory])

    with patch("src.simulation.engine.FactoryRepository") as MockFactoryRepo:
        mock_factory_repo = AsyncMock()
        MockFactoryRepo.return_value = mock_factory_repo

        engine = make_engine()
        engine._tick = 1
        await engine._apply_physics(world_state)

    # Stock should increase by production_rate_current = 10.0
    mock_factory_repo.update_product_stock.assert_called_once_with(
        "f-001", "mat-001", pytest.approx(10.0)
    )


@pytest.mark.asyncio
async def test_apply_physics_zeros_production_when_stock_max_reached():
    factory = Factory(
        id="f-001",
        name="Factory 1",
        lat=-22.9,
        lng=-47.1,
        status=FactoryStatus.OPERATING,
        products={
            "mat-001": FactoryProduct(
                stock=200.0,
                stock_reserved=0.0,
                stock_max=200.0,
                production_rate_max=10.0,
                production_rate_current=10.0,
            )
        },
        partner_warehouses=[],
    )
    world_state = make_world_state(factories=[factory])

    with patch("src.simulation.engine.FactoryRepository") as MockFactoryRepo:
        mock_factory_repo = AsyncMock()
        MockFactoryRepo.return_value = mock_factory_repo

        engine = make_engine()
        engine._tick = 1
        await engine._apply_physics(world_state)

    mock_factory_repo.update_production_rate.assert_called_once_with(
        "f-001", "mat-001", 0.0
    )
    # No stock update should be applied when production is zeroed
    mock_factory_repo.update_product_stock.assert_not_called()


# ---------------------------------------------------------------------------
# _apply_physics — truck degradation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_physics_increments_truck_degradation():
    truck = make_truck(
        status=TruckStatus.IN_TRANSIT,
        degradation=0.1,
        capacity_tons=20.0,
        cargo=TruckCargo(
            material_id="mat-001",
            quantity_tons=10.0,
            origin_type=RouteNodeType.FACTORY,
            origin_id="f-001",
            destination_type=RouteNodeType.WAREHOUSE,
            destination_id="w-001",
        ),
    )
    world_state = make_world_state(trucks=[truck])

    mock_route = MagicMock()
    mock_route.id = "route-001"
    mock_route.eta_ticks = 3
    mock_route.path = [[-46.6, -23.5], [-45.8, -22.8]]
    mock_route.timestamps = [0, 4]

    with patch("src.simulation.engine.TruckRepository") as MockTruckRepo, \
         patch("src.simulation.engine.RouteRepository") as MockRouteRepo:
        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo
        mock_route_repo = AsyncMock()
        mock_route_repo.get_active_by_truck.return_value = mock_route
        MockRouteRepo.return_value = mock_route_repo

        engine = make_engine()
        engine._tick = 2
        await engine._apply_physics(world_state)

    mock_truck_repo.update_degradation.assert_called_once()
    _, new_degradation, new_breakdown_risk = (
        mock_truck_repo.update_degradation.call_args[0]
    )
    assert new_degradation > 0.1
    assert new_breakdown_risk < 0.07


@pytest.mark.asyncio
async def test_apply_physics_blocks_trip_when_degradation_above_95_pct():
    truck = make_truck(
        status=TruckStatus.IN_TRANSIT,
        degradation=0.95,
        active_route=TruckRoute(
            route_id="route-001",
            path=[[-46.6, -23.5], [-45.8, -22.8]],
            timestamps=[0, 4],
            eta_ticks=2,
        ),
        cargo=TruckCargo(
            material_id="mat-001",
            quantity_tons=10.0,
            origin_type=RouteNodeType.FACTORY,
            origin_id="f-001",
            destination_type=RouteNodeType.WAREHOUSE,
            destination_id="w-001",
        ),
    )
    world_state = make_world_state(trucks=[truck])

    with patch("src.simulation.engine.TruckRepository") as MockTruckRepo, \
         patch("src.simulation.engine.RouteRepository") as MockRouteRepo, \
         patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.publish_event", new_callable=AsyncMock) as mock_publish:
        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo

        mock_route_repo = AsyncMock()
        mock_active_route = MagicMock()
        mock_active_route.id = "route-001"
        mock_route_repo.get_active_by_truck.return_value = mock_active_route
        MockRouteRepo.return_value = mock_route_repo

        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo

        engine = make_engine()
        engine._tick = 2
        await engine._apply_physics(world_state)

    mock_truck_repo.update_status.assert_any_call("truck-001", "broken")
    mock_truck_repo.set_cargo.assert_called_once_with("truck-001", None)
    mock_truck_repo.set_active_route.assert_called_once_with("truck-001", None)
    mock_route_repo.update_status.assert_called_once_with("route-001", "interrupted")

    mock_publish.assert_called_once()
    published_event = mock_publish.call_args[0][0]
    assert published_event.event_type == "engine_blocked_degraded_truck"
    assert published_event.entity_id == "truck-001"


# ---------------------------------------------------------------------------
# _apply_physics — pending order age
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_physics_increments_pending_order_age():
    world_state = make_world_state()

    with patch("src.simulation.engine.OrderRepository") as MockOrderRepo:
        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo

        engine = make_engine()
        engine._tick = 1
        await engine._apply_physics(world_state)

    mock_order_repo.increment_all_age_ticks.assert_called_once()


# ---------------------------------------------------------------------------
# _evaluate_triggers — stores
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_triggers_wakes_store_when_projected_stockout():
    # stock=5.0, reorder_point=4.0, demand_rate=1.0, lead_time_ticks=3
    # (5.0 - 4.0) / 1.0 = 1.0 < 3 × 1.5 = 4.5 → trigger active
    store = make_store(
        stocks={"mat-001": StoreStock(stock=5.0, demand_rate=1.0, reorder_point=4.0)}
    )
    warehouse = make_warehouse()
    world_state = make_world_state(stores=[store], warehouses=[warehouse])

    engine = make_engine()
    engine._tick = 1

    with patch.object(engine, "_estimate_lead_time_ticks", return_value=3):
        with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
             patch("src.simulation.engine.OrderRepository") as MockOrderRepo:
            mock_event_repo = AsyncMock()
            MockEventRepo.return_value = mock_event_repo
            mock_event_repo.get_active_for_entity.return_value = []

            mock_order_repo = AsyncMock()
            MockOrderRepo.return_value = mock_order_repo
            mock_order_repo.get_untriggered_for_target.return_value = []
            mock_order_repo.get_triggered_but_pending_for_target.return_value = []

            triggers = await engine._evaluate_triggers(world_state)

    assert len(triggers) >= 1
    triggered_entities = [t[1].entity_id for t in triggers]
    assert "store-001" in triggered_entities


@pytest.mark.asyncio
async def test_evaluate_triggers_does_not_wake_store_when_stock_ok():
    # stock=20.0, reorder_point=4.0, demand_rate=1.0, lead_time_ticks=3
    # (20.0 - 4.0) / 1.0 = 16.0 < 4.5 → False → no trigger
    store = make_store(
        stocks={"mat-001": StoreStock(stock=20.0, demand_rate=1.0, reorder_point=4.0)}
    )
    warehouse = make_warehouse()
    world_state = make_world_state(stores=[store], warehouses=[warehouse])

    engine = make_engine()
    engine._tick = 1

    with patch.object(engine, "_estimate_lead_time_ticks", return_value=3):
        with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
             patch("src.simulation.engine.OrderRepository") as MockOrderRepo, \
             patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
            mock_event_repo = AsyncMock()
            MockEventRepo.return_value = mock_event_repo
            mock_event_repo.get_active_for_entity.return_value = []
            mock_event_repo.get_active_by_type.return_value = []

            mock_order_repo = AsyncMock()
            MockOrderRepo.return_value = mock_order_repo
            mock_order_repo.get_untriggered_for_target.return_value = []
            mock_order_repo.get_triggered_but_pending_for_target.return_value = []
            mock_order_repo.get_confirmed_without_route.return_value = []
            mock_order_repo.get_retry_eligible.return_value = []

            mock_truck_repo = AsyncMock()
            MockTruckRepo.return_value = mock_truck_repo

            triggers = await engine._evaluate_triggers(world_state)

    store_triggers = [t for t in triggers if t[1].entity_id == "store-001"]
    assert len(store_triggers) == 0


# ---------------------------------------------------------------------------
# _evaluate_triggers — trucks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_triggers_wakes_truck_on_pending_event():
    truck = make_truck(id="truck-001", status=TruckStatus.IN_TRANSIT)
    world_state = make_world_state(trucks=[truck])

    pending_event = MagicMock()
    pending_event.event_type = "route_blocked"

    engine = make_engine()
    engine._tick = 1

    with patch.object(engine, "_estimate_lead_time_ticks", return_value=3):
        with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
             patch("src.simulation.engine.OrderRepository") as MockOrderRepo:
            mock_event_repo = AsyncMock()
            MockEventRepo.return_value = mock_event_repo
            mock_event_repo.get_active_for_entity.return_value = [pending_event]

            mock_order_repo = AsyncMock()
            MockOrderRepo.return_value = mock_order_repo
            mock_order_repo.get_untriggered_for_target.return_value = []
            mock_order_repo.get_triggered_but_pending_for_target.return_value = []

            triggers = await engine._evaluate_triggers(world_state)

    truck_triggers = [t for t in triggers if t[1].entity_id == "truck-001"]
    assert len(truck_triggers) == 1


@pytest.mark.asyncio
async def test_evaluate_triggers_does_not_wake_truck_in_transit_without_event():
    truck = make_truck(id="truck-001", status=TruckStatus.IN_TRANSIT)
    world_state = make_world_state(trucks=[truck])

    engine = make_engine()
    engine._tick = 1

    with patch.object(engine, "_estimate_lead_time_ticks", return_value=3):
        with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
             patch("src.simulation.engine.OrderRepository") as MockOrderRepo:
            mock_event_repo = AsyncMock()
            MockEventRepo.return_value = mock_event_repo
            mock_event_repo.get_active_for_entity.return_value = []

            mock_order_repo = AsyncMock()
            MockOrderRepo.return_value = mock_order_repo
            mock_order_repo.get_untriggered_for_target.return_value = []
            mock_order_repo.get_triggered_but_pending_for_target.return_value = []

            triggers = await engine._evaluate_triggers(world_state)

    truck_triggers = [t for t in triggers if t[1].entity_id == "truck-001"]
    assert len(truck_triggers) == 0


# ---------------------------------------------------------------------------
# run_tick — fire-and-forget + semaphore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_does_not_block_on_agent_tasks():
    task_started = asyncio.Event()
    task_completed = asyncio.Event()

    async def slow_agent(event):
        task_started.set()
        await asyncio.sleep(0.05)
        task_completed.set()

    agent_fn = slow_agent
    dummy_event = MagicMock()
    dummy_event.entity_id = "store-001"

    world_state = make_world_state()

    engine = make_engine()

    with patch(
        "src.services.world_state.WorldStateService"
    ) as MockWSService:
        mock_ws_instance = AsyncMock()
        mock_ws_instance.load.return_value = world_state
        MockWSService.return_value = mock_ws_instance

        with patch.object(engine, "_apply_physics", new_callable=AsyncMock):
            with patch.object(
                engine, "_evaluate_triggers", new_callable=AsyncMock
            ) as mock_triggers:
                mock_triggers.return_value = [(agent_fn, dummy_event)]
                with patch(
                    "src.simulation.engine.publish_world_state", new_callable=AsyncMock
                ):
                    with patch(
                        "asyncio.create_task", wraps=asyncio.create_task
                    ) as mock_create_task:
                        await engine.run_tick()

    # create_task must have been called (not await)
    mock_create_task.assert_called()
    # run_tick returned before the slow_agent completed
    assert not task_completed.is_set()


@pytest.mark.asyncio
async def test_semaphore_limits_agent_concurrency():
    concurrent_count = 0
    max_concurrent = 0
    results = []

    async def tracked_agent(event):
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)
        await asyncio.sleep(0.01)
        concurrent_count -= 1
        results.append("done")

    dummy_event = MagicMock()
    engine = make_engine(max_workers=1)

    t1 = asyncio.create_task(engine._dispatch_agent(tracked_agent, dummy_event))
    t2 = asyncio.create_task(engine._dispatch_agent(tracked_agent, dummy_event))
    await asyncio.gather(t1, t2)

    assert max_concurrent == 1
    assert len(results) == 2


# ---------------------------------------------------------------------------
# SimulationEngine._is_valid_path — guard against corrupted route.path JSONB
# ---------------------------------------------------------------------------


def test_is_valid_path_accepts_list_of_pairs():
    assert SimulationEngine._is_valid_path([[-46.6, -23.5], [-46.7, -23.4]]) is True


def test_is_valid_path_rejects_string_polyline_encoded():
    assert SimulationEngine._is_valid_path("podfk@fhimxAbUgl") is False


def test_is_valid_path_rejects_none_and_empty():
    assert SimulationEngine._is_valid_path(None) is False
    assert SimulationEngine._is_valid_path([]) is False
    assert SimulationEngine._is_valid_path([[-46.6, -23.5]]) is False


def test_is_valid_path_rejects_malformed_points():
    assert SimulationEngine._is_valid_path([[-46.6]]) is False
    assert SimulationEngine._is_valid_path([[-46.6, -23.5], "junk"]) is False


# ---------------------------------------------------------------------------
# In-flight agent dedup — skip trigger when previous cycle still running
# ---------------------------------------------------------------------------


def _schedule_trigger(engine, event, agent_fn):
    """Mirror the dispatch+dedup block from SimulationEngine.run_tick."""
    key = (event.entity_type, event.entity_id)
    existing = engine._in_flight_by_entity.get(key)
    if existing is not None:
        existing_task, started_tick = existing
        if not existing_task.done() and started_tick < engine._tick:
            return None
    task = asyncio.create_task(engine._dispatch_agent(agent_fn, event))
    engine._pending_agent_tasks.add(task)
    engine._in_flight_by_entity[key] = (task, engine._tick)
    task.add_done_callback(engine._pending_agent_tasks.discard)
    task.add_done_callback(lambda t, k=key: engine._clear_in_flight_if(k, t))
    return task


@pytest.mark.asyncio
async def test_dispatch_dedup_skips_second_trigger_for_same_entity_while_in_flight():
    from src.simulation.events import SimulationEvent

    engine = make_engine()
    gate = asyncio.Event()
    call_count = {"n": 0}

    async def slow_agent(_event):
        call_count["n"] += 1
        await gate.wait()

    def event_at(tick):
        return SimulationEvent(
            event_type="low_stock_trigger", source="engine",
            entity_type="store", entity_id="store-001",
            payload={}, tick=tick,
        )

    engine._tick = 1
    t1 = _schedule_trigger(engine, event_at(1), slow_agent)
    await asyncio.sleep(0.01)
    assert t1 is not None
    assert call_count["n"] == 1

    engine._tick = 2
    t2 = _schedule_trigger(engine, event_at(2), slow_agent)
    assert t2 is None, "dedup must skip while previous tick's task still running"
    assert call_count["n"] == 1

    gate.set()
    await engine.drain_pending_agents()

    gate.clear()
    engine._tick = 3
    t3 = _schedule_trigger(engine, event_at(3), slow_agent)
    await asyncio.sleep(0.01)
    assert t3 is not None, "after previous task completed, next trigger must fire"
    assert call_count["n"] == 2

    gate.set()
    await engine.drain_pending_agents()


@pytest.mark.asyncio
async def test_dispatch_dedup_allows_multiple_triggers_same_entity_same_tick():
    from src.simulation.events import SimulationEvent

    engine = make_engine()
    gate = asyncio.Event()
    call_count = {"n": 0}

    async def slow_agent(_event):
        call_count["n"] += 1
        await gate.wait()

    engine._tick = 5
    ev_low = SimulationEvent(
        event_type="low_stock_trigger", source="engine",
        entity_type="store", entity_id="store-001",
        payload={}, tick=5,
    )
    ev_resupply = SimulationEvent(
        event_type="resupply_delivered", source="engine",
        entity_type="store", entity_id="store-001",
        payload={"material_id": "cimento"}, tick=5,
    )

    t1 = _schedule_trigger(engine, ev_low, slow_agent)
    t2 = _schedule_trigger(engine, ev_resupply, slow_agent)
    await asyncio.sleep(0.01)
    assert t1 is not None and t2 is not None
    assert call_count["n"] == 2, "both triggers for same entity within same tick must dispatch"

    gate.set()
    await engine.drain_pending_agents()


@pytest.mark.asyncio
async def test_dispatch_dedup_allows_different_entities_concurrently():
    from src.simulation.events import SimulationEvent

    engine = make_engine()
    gate = asyncio.Event()
    call_count = {"n": 0}

    async def slow_agent(_event):
        call_count["n"] += 1
        await gate.wait()

    ev_a = SimulationEvent(
        event_type="low_stock_trigger", source="engine",
        entity_type="store", entity_id="store-001",
        payload={}, tick=1,
    )
    ev_b = SimulationEvent(
        event_type="low_stock_trigger", source="engine",
        entity_type="store", entity_id="store-002",
        payload={}, tick=1,
    )

    _schedule_trigger(engine, ev_a, slow_agent)
    _schedule_trigger(engine, ev_b, slow_agent)
    await asyncio.sleep(0.01)
    assert call_count["n"] == 2, "different entities should run concurrently"

    gate.set()
    await engine.drain_pending_agents()
