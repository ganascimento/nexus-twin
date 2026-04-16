from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4

import pytest

from src.enums import RouteNodeType, TruckStatus, TruckType
from src.simulation.engine import SimulationEngine
from src.world.entities.truck import Truck, TruckCargo
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


def make_cargo(material_id="cimento", quantity_tons=50):
    return TruckCargo(
        material_id=material_id,
        quantity_tons=quantity_tons,
        origin_type=RouteNodeType.FACTORY,
        origin_id="factory_01",
        destination_type=RouteNodeType.WAREHOUSE,
        destination_id="wh_01",
    )


def make_truck(**kwargs):
    defaults = dict(
        id="truck_01",
        truck_type=TruckType.TERCEIRO,
        capacity_tons=30.0,
        base_lat=-23.5,
        base_lng=-46.6,
        current_lat=-23.5,
        current_lng=-46.6,
        degradation=0.1,
        breakdown_risk=0.01,
        status=TruckStatus.IN_TRANSIT,
    )
    defaults.update(kwargs)
    return Truck(**defaults)


def make_route(
    id=None,
    truck_id="truck_01",
    dest_type="warehouse",
    dest_id="wh_01",
    eta_ticks=1,
    order_id=None,
    path=None,
    timestamps=None,
    status="active",
    origin_type="factory",
    origin_id="factory_01",
):
    route = MagicMock()
    route.id = id or uuid4()
    route.truck_id = truck_id
    route.origin_type = origin_type
    route.origin_id = origin_id
    route.dest_type = dest_type
    route.dest_id = dest_id
    route.eta_ticks = eta_ticks
    route.order_id = order_id
    route.path = path or [[-46.6, -23.5], [-45.8, -22.8]]
    route.timestamps = timestamps or [0, 4]
    route.status = status
    return route


def make_engine():
    redis_client = AsyncMock()
    mock_session = AsyncMock()

    @asynccontextmanager
    async def session_factory():
        yield mock_session

    engine = SimulationEngine(redis_client, session_factory)
    return engine, mock_session


def _patch_repos():
    return (
        patch("src.simulation.engine.TruckRepository"),
        patch("src.simulation.engine.StoreRepository"),
        patch("src.simulation.engine.FactoryRepository"),
        patch("src.simulation.engine.OrderRepository"),
        patch("src.simulation.engine.RouteRepository"),
        patch("src.simulation.engine.EventRepository"),
        patch("src.simulation.engine.WarehouseRepository"),
    )


def _setup_mocks(
    MockTruckRepo,
    MockStoreRepo,
    MockFactoryRepo,
    MockOrderRepo,
    MockRouteRepo,
    MockEventRepo,
    MockWarehouseRepo,
    route,
):
    mock_truck_repo = AsyncMock()
    MockTruckRepo.return_value = mock_truck_repo

    mock_store_repo = AsyncMock()
    MockStoreRepo.return_value = mock_store_repo

    mock_factory_repo = AsyncMock()
    MockFactoryRepo.return_value = mock_factory_repo

    mock_order_repo = AsyncMock()
    MockOrderRepo.return_value = mock_order_repo

    mock_route_repo = AsyncMock()
    mock_route_repo.get_active_by_truck.return_value = route
    MockRouteRepo.return_value = mock_route_repo

    mock_event_repo = AsyncMock()
    MockEventRepo.return_value = mock_event_repo

    mock_warehouse_repo = AsyncMock()
    MockWarehouseRepo.return_value = mock_warehouse_repo

    return (
        mock_truck_repo,
        mock_store_repo,
        mock_factory_repo,
        mock_order_repo,
        mock_route_repo,
        mock_event_repo,
        mock_warehouse_repo,
    )


# ---------------------------------------------------------------------------
# Stock transfer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_arrival_transfers_stock_to_warehouse():
    truck = make_truck(
        cargo=make_cargo("cimento", 50),
    )
    route = make_route(dest_type="warehouse", dest_id="wh_01", eta_ticks=1)
    world_state = make_world_state(trucks=[truck])

    engine, _ = make_engine()
    engine._tick = 5

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR, route)
        mock_warehouse_repo = mocks[6]

        await engine._apply_physics(world_state)

    mock_warehouse_repo.update_stock.assert_called_once_with("wh_01", "cimento", 50)


@pytest.mark.asyncio
async def test_arrival_transfers_stock_to_store():
    truck = make_truck(
        cargo=make_cargo("cimento", 30),
    )
    route = make_route(dest_type="store", dest_id="store_01", eta_ticks=1)
    world_state = make_world_state(trucks=[truck])

    engine, _ = make_engine()
    engine._tick = 5

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR, route)
        mock_store_repo = mocks[1]

        await engine._apply_physics(world_state)

    mock_store_repo.update_stock.assert_called_once_with("store_01", "cimento", 30)


@pytest.mark.asyncio
async def test_arrival_empty_cargo_skips_transfer():
    truck = make_truck(cargo=None)
    route = make_route(dest_type="warehouse", dest_id="wh_01", eta_ticks=1)
    world_state = make_world_state(trucks=[truck])

    engine, _ = make_engine()
    engine._tick = 5

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR, route)
        mock_warehouse_repo = mocks[6]

        await engine._apply_physics(world_state)

    mock_warehouse_repo.update_stock.assert_not_called()


@pytest.mark.asyncio
async def test_arrival_unknown_dest_type_logs_warning():
    truck = make_truck(
        cargo=make_cargo("cimento", 50),
    )
    route = make_route(dest_type="factory", dest_id="factory_01", eta_ticks=1)
    world_state = make_world_state(trucks=[truck])

    engine, _ = make_engine()
    engine._tick = 5

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR, route)
        mock_warehouse_repo = mocks[6]
        mock_store_repo = mocks[1]

        await engine._apply_physics(world_state)

    mock_warehouse_repo.update_stock.assert_not_called()
    mock_store_repo.update_stock.assert_not_called()


# ---------------------------------------------------------------------------
# Order completion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_arrival_marks_order_delivered():
    order_id = uuid4()
    truck = make_truck(
        cargo=make_cargo("cimento", 50),
    )
    route = make_route(dest_type="warehouse", dest_id="wh_01", eta_ticks=1, order_id=order_id)
    world_state = make_world_state(trucks=[truck])

    engine, _ = make_engine()
    engine._tick = 5

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR, route)
        mock_order_repo = mocks[3]

        await engine._apply_physics(world_state)

    mock_order_repo.update_status.assert_called_once_with(order_id, "delivered")


@pytest.mark.asyncio
async def test_arrival_no_order_skips_completion():
    truck = make_truck(
        cargo=make_cargo("cimento", 50),
    )
    route = make_route(dest_type="warehouse", dest_id="wh_01", eta_ticks=1, order_id=None)
    world_state = make_world_state(trucks=[truck])

    engine, _ = make_engine()
    engine._tick = 5

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR, route)
        mock_order_repo = mocks[3]

        await engine._apply_physics(world_state)

    mock_order_repo.update_status.assert_not_called()


# ---------------------------------------------------------------------------
# Events creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_arrival_creates_resupply_delivered_event_for_warehouse():
    truck = make_truck(
        cargo=make_cargo("cimento", 50),
    )
    route = make_route(dest_type="warehouse", dest_id="wh_01", eta_ticks=1)
    world_state = make_world_state(trucks=[truck])

    engine, _ = make_engine()
    engine._tick = 5

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR, route)
        mock_event_repo = mocks[5]

        await engine._apply_physics(world_state)

    event_calls = mock_event_repo.create.call_args_list
    resupply_calls = [
        c for c in event_calls
        if c[0][0].get("event_type") == "resupply_delivered"
    ]
    assert len(resupply_calls) == 1
    event_data = resupply_calls[0][0][0]
    assert event_data["entity_type"] == "warehouse"
    assert event_data["entity_id"] == "wh_01"
    assert event_data["source"] == "engine"
    assert event_data["status"] == "active"


@pytest.mark.asyncio
async def test_arrival_creates_resupply_delivered_event_for_store():
    truck = make_truck(
        cargo=make_cargo("cimento", 30),
    )
    route = make_route(dest_type="store", dest_id="store_01", eta_ticks=1)
    world_state = make_world_state(trucks=[truck])

    engine, _ = make_engine()
    engine._tick = 5

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR, route)
        mock_event_repo = mocks[5]

        await engine._apply_physics(world_state)

    event_calls = mock_event_repo.create.call_args_list
    resupply_calls = [
        c for c in event_calls
        if c[0][0].get("event_type") == "resupply_delivered"
    ]
    assert len(resupply_calls) == 1
    assert resupply_calls[0][0][0]["entity_type"] == "store"
    assert resupply_calls[0][0][0]["entity_id"] == "store_01"


@pytest.mark.asyncio
async def test_arrival_creates_truck_arrived_event():
    truck = make_truck(
        cargo=make_cargo("cimento", 50),
    )
    route = make_route(dest_type="warehouse", dest_id="wh_01", eta_ticks=1)
    world_state = make_world_state(trucks=[truck])

    engine, _ = make_engine()
    engine._tick = 5

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR, route)
        mock_event_repo = mocks[5]

        await engine._apply_physics(world_state)

    event_calls = mock_event_repo.create.call_args_list
    arrived_calls = [
        c for c in event_calls
        if c[0][0].get("event_type") == "truck_arrived"
    ]
    assert len(arrived_calls) == 1
    event_data = arrived_calls[0][0][0]
    assert event_data["entity_type"] == "truck"
    assert event_data["entity_id"] == "truck_01"


@pytest.mark.asyncio
async def test_arrival_event_payload_contains_delivery_data():
    truck = make_truck(
        cargo=make_cargo("cimento", 50),
    )
    route = make_route(dest_type="warehouse", dest_id="wh_01", eta_ticks=1)
    world_state = make_world_state(trucks=[truck])

    engine, _ = make_engine()
    engine._tick = 5

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR, route)
        mock_event_repo = mocks[5]

        await engine._apply_physics(world_state)

    event_calls = mock_event_repo.create.call_args_list

    resupply_payload = [
        c[0][0]["payload"] for c in event_calls
        if c[0][0].get("event_type") == "resupply_delivered"
    ][0]
    assert resupply_payload["material_id"] == "cimento"
    assert resupply_payload["quantity_tons"] == 50
    assert resupply_payload["from_truck_id"] == "truck_01"

    arrived_payload = [
        c[0][0]["payload"] for c in event_calls
        if c[0][0].get("event_type") == "truck_arrived"
    ][0]
    assert arrived_payload["route_id"] == str(route.id)
    assert arrived_payload["dest_type"] == "warehouse"
    assert arrived_payload["dest_id"] == "wh_01"


# ---------------------------------------------------------------------------
# Truck state cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_arrival_clears_truck_state():
    truck = make_truck(
        cargo=make_cargo("cimento", 50),
    )
    route = make_route(dest_type="warehouse", dest_id="wh_01", eta_ticks=1)
    world_state = make_world_state(trucks=[truck])

    engine, _ = make_engine()
    engine._tick = 5

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR, route)
        mock_truck_repo = mocks[0]
        mock_route_repo = mocks[4]

        await engine._apply_physics(world_state)

    mock_truck_repo.set_cargo.assert_called_once_with("truck_01", None)
    mock_truck_repo.update_status.assert_called_once_with("truck_01", "idle")
    mock_truck_repo.set_active_route.assert_called_once_with("truck_01", None)
    mock_route_repo.update_status.assert_called_once()


@pytest.mark.asyncio
async def test_arrival_reads_cargo_before_clearing():
    truck = make_truck(
        cargo=make_cargo("cimento", 50),
    )
    route = make_route(dest_type="warehouse", dest_id="wh_01", eta_ticks=1)
    world_state = make_world_state(trucks=[truck])

    engine, _ = make_engine()
    engine._tick = 5

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR, route)
        mock_truck_repo = mocks[0]
        mock_warehouse_repo = mocks[6]

        await engine._apply_physics(world_state)

    wh_update_call = mock_warehouse_repo.update_stock.call_args_list
    set_cargo_call = mock_truck_repo.set_cargo.call_args_list

    assert len(wh_update_call) == 1
    assert len(set_cargo_call) == 1
    assert wh_update_call[0][0] == ("wh_01", "cimento", 50)
    assert set_cargo_call[0][0] == ("truck_01", None)
