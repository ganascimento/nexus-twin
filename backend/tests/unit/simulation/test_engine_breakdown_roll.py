from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
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


def make_cargo():
    return TruckCargo(
        material_id="cimento",
        quantity_tons=50,
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
        degradation=0.8,
        breakdown_risk=0.3,
        status=TruckStatus.IN_TRANSIT,
        cargo=make_cargo(),
    )
    defaults.update(kwargs)
    return Truck(**defaults)


def make_route(**kwargs):
    route = MagicMock()
    route.id = kwargs.get("id", uuid4())
    route.truck_id = kwargs.get("truck_id", "truck_01")
    route.dest_type = kwargs.get("dest_type", "warehouse")
    route.dest_id = kwargs.get("dest_id", "wh_01")
    route.eta_ticks = kwargs.get("eta_ticks", 5)
    route.order_id = kwargs.get("order_id", None)
    route.path = kwargs.get("path", [[-46.6, -23.5], [-45.8, -22.8]])
    route.timestamps = kwargs.get("timestamps", [0, 10])
    route.status = kwargs.get("status", "active")
    return route


def make_engine():
    redis_client = AsyncMock()
    mock_session = AsyncMock()

    @asynccontextmanager
    async def session_factory():
        yield mock_session

    engine = SimulationEngine(redis_client, session_factory)
    return engine


@pytest.mark.asyncio
async def test_breakdown_roll_creates_event():
    truck = make_truck(degradation=0.8, breakdown_risk=0.3)
    route = make_route(eta_ticks=5)
    world_state = make_world_state(trucks=[truck])

    engine = make_engine()
    engine._tick = 5

    with patch("src.simulation.engine.TruckRepository") as MTR, \
         patch("src.simulation.engine.StoreRepository") as MSR, \
         patch("src.simulation.engine.FactoryRepository") as MFR, \
         patch("src.simulation.engine.OrderRepository") as MOR, \
         patch("src.simulation.engine.RouteRepository") as MRR, \
         patch("src.simulation.engine.EventRepository") as MER, \
         patch("src.simulation.engine.WarehouseRepository") as MWR, \
         patch("src.simulation.engine.roll_breakdown", return_value=True):
        mock_truck_repo = AsyncMock()
        MTR.return_value = mock_truck_repo
        MSR.return_value = AsyncMock()
        MFR.return_value = AsyncMock()
        MOR.return_value = AsyncMock()

        mock_route_repo = AsyncMock()
        mock_route_repo.get_active_by_truck.return_value = route
        MRR.return_value = mock_route_repo

        mock_event_repo = AsyncMock()
        MER.return_value = mock_event_repo
        MWR.return_value = AsyncMock()

        await engine._apply_physics(world_state)

    mock_truck_repo.update_status.assert_any_call("truck_01", "broken")

    event_calls = mock_event_repo.create.call_args_list
    breakdown_calls = [
        c for c in event_calls
        if c[0][0].get("event_type") == "truck_breakdown"
    ]
    assert len(breakdown_calls) == 1
    assert breakdown_calls[0][0][0]["entity_id"] == "truck_01"


@pytest.mark.asyncio
async def test_no_breakdown_when_roll_passes():
    truck = make_truck(degradation=0.3, breakdown_risk=0.02)
    route = make_route(eta_ticks=5)
    world_state = make_world_state(trucks=[truck])

    engine = make_engine()
    engine._tick = 5

    with patch("src.simulation.engine.TruckRepository") as MTR, \
         patch("src.simulation.engine.StoreRepository") as MSR, \
         patch("src.simulation.engine.FactoryRepository") as MFR, \
         patch("src.simulation.engine.OrderRepository") as MOR, \
         patch("src.simulation.engine.RouteRepository") as MRR, \
         patch("src.simulation.engine.EventRepository") as MER, \
         patch("src.simulation.engine.WarehouseRepository") as MWR, \
         patch("src.simulation.engine.roll_breakdown", return_value=False):
        mock_truck_repo = AsyncMock()
        MTR.return_value = mock_truck_repo
        MSR.return_value = AsyncMock()
        MFR.return_value = AsyncMock()
        MOR.return_value = AsyncMock()

        mock_route_repo = AsyncMock()
        mock_route_repo.get_active_by_truck.return_value = route
        MRR.return_value = mock_route_repo

        mock_event_repo = AsyncMock()
        MER.return_value = mock_event_repo
        MWR.return_value = AsyncMock()

        await engine._apply_physics(world_state)

    broken_calls = [
        c for c in mock_truck_repo.update_status.call_args_list
        if c[0] == ("truck_01", "broken")
    ]
    assert len(broken_calls) == 0


@pytest.mark.asyncio
async def test_breakdown_skipped_when_risk_zero():
    truck = make_truck(degradation=0.0, breakdown_risk=0.0)
    route = make_route(eta_ticks=5)
    world_state = make_world_state(trucks=[truck])

    engine = make_engine()
    engine._tick = 5

    with patch("src.simulation.engine.TruckRepository") as MTR, \
         patch("src.simulation.engine.StoreRepository") as MSR, \
         patch("src.simulation.engine.FactoryRepository") as MFR, \
         patch("src.simulation.engine.OrderRepository") as MOR, \
         patch("src.simulation.engine.RouteRepository") as MRR, \
         patch("src.simulation.engine.EventRepository") as MER, \
         patch("src.simulation.engine.WarehouseRepository") as MWR, \
         patch("src.simulation.engine.roll_breakdown", return_value=False) as mock_roll:
        mock_truck_repo = AsyncMock()
        MTR.return_value = mock_truck_repo
        MSR.return_value = AsyncMock()
        MFR.return_value = AsyncMock()
        MOR.return_value = AsyncMock()

        mock_route_repo = AsyncMock()
        mock_route_repo.get_active_by_truck.return_value = route
        MRR.return_value = mock_route_repo

        MER.return_value = AsyncMock()
        MWR.return_value = AsyncMock()

        await engine._apply_physics(world_state)

    broken_calls = [
        c for c in mock_truck_repo.update_status.call_args_list
        if c[0] == ("truck_01", "broken")
    ]
    assert len(broken_calls) == 0
