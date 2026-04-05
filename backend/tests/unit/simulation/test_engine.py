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


def make_engine(
    world_state_service=None, redis_client=None, session_factory=None, max_workers=4
):
    ws_service = world_state_service or AsyncMock()
    rc = redis_client or AsyncMock()

    if session_factory is None:
        mock_session = AsyncMock()

        @asynccontextmanager
        async def _session_factory():
            yield mock_session

        session_factory = _session_factory

    engine = SimulationEngine(ws_service, rc, session_factory)
    engine._semaphore = asyncio.Semaphore(max_workers)
    return engine


# ---------------------------------------------------------------------------
# _apply_physics — truck position
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_physics_advances_truck_position():
    # path is [lng, lat] pairs; route spans ticks 0→4
    # At engine._tick=2 the truck is at the midpoint
    truck = make_truck(
        status=TruckStatus.IN_TRANSIT,
        active_route=TruckRoute(
            route_id="route-001",
            path=[[-46.6, -23.5], [-45.8, -22.8]],  # [lng, lat]
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

    with patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo

        engine = make_engine()
        engine._tick = 2
        await engine._apply_physics(world_state)

    mock_truck_repo.update_position.assert_called_once()
    call_args = mock_truck_repo.update_position.call_args[0]
    truck_id, new_lat, new_lng = call_args
    assert truck_id == "truck-001"
    # Midpoint interpolation: lng = -46.6 + 0.5*(-45.8-(-46.6)) = -46.2; lat = -23.5 + 0.5*(-22.8-(-23.5)) = -23.15
    assert new_lat == pytest.approx(-23.15, abs=1e-6)
    assert new_lng == pytest.approx(-46.2, abs=1e-6)


@pytest.mark.asyncio
async def test_apply_physics_marks_truck_arrived_when_route_complete():
    truck = make_truck(
        status=TruckStatus.IN_TRANSIT,
        active_route=TruckRoute(
            route_id="route-001",
            path=[[-46.6, -23.5], [-45.8, -22.8]],
            timestamps=[0, 2],
            eta_ticks=0,
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

    with patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo

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

    with patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo

        engine = make_engine()
        engine._tick = 2
        await engine._apply_physics(world_state)

    mock_truck_repo.update_degradation.assert_called_once()
    _, new_degradation, new_breakdown_risk = (
        mock_truck_repo.update_degradation.call_args[0]
    )
    assert new_degradation > 0.1
    # At degradation ~0.1 (below 0.7 threshold), breakdown risk is low
    assert new_breakdown_risk < 0.07


@pytest.mark.asyncio
async def test_apply_physics_blocks_trip_when_degradation_above_95_pct():
    # Truck is in_transit with degradation >= 0.95 — engine must forcibly mark it idle
    # and publish a blocking event
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

    with patch("src.simulation.engine.TruckRepository") as MockTruckRepo:
        mock_truck_repo = AsyncMock()
        MockTruckRepo.return_value = mock_truck_repo
        with patch(
            "src.simulation.engine.publish_event", new_callable=AsyncMock
        ) as mock_publish:
            engine = make_engine()
            engine._tick = 2
            await engine._apply_physics(world_state)

    mock_truck_repo.update_status.assert_called_once_with("truck-001", "idle")
    mock_truck_repo.update_position.assert_not_called()

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
        with patch("src.simulation.engine.EventRepository") as MockEventRepo:
            mock_event_repo = AsyncMock()
            MockEventRepo.return_value = mock_event_repo
            mock_event_repo.get_active_for_entity.return_value = []

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
        with patch("src.simulation.engine.EventRepository") as MockEventRepo:
            mock_event_repo = AsyncMock()
            MockEventRepo.return_value = mock_event_repo
            mock_event_repo.get_active_for_entity.return_value = []

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
        with patch("src.simulation.engine.EventRepository") as MockEventRepo:
            mock_event_repo = AsyncMock()
            MockEventRepo.return_value = mock_event_repo
            mock_event_repo.get_active_for_entity.return_value = [pending_event]

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
        with patch("src.simulation.engine.EventRepository") as MockEventRepo:
            mock_event_repo = AsyncMock()
            MockEventRepo.return_value = mock_event_repo
            mock_event_repo.get_active_for_entity.return_value = []

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

    ws_service = AsyncMock()
    world_state = make_world_state()
    ws_service.load.return_value = world_state

    engine = make_engine(world_state_service=ws_service)

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
