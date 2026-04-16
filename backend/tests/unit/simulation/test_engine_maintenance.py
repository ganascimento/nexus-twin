from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.enums import TruckStatus, TruckType
from src.simulation.engine import SimulationEngine
from src.world.entities.truck import Truck
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


def make_truck(**kwargs):
    defaults = dict(
        id="truck_01",
        truck_type=TruckType.TERCEIRO,
        capacity_tons=30.0,
        base_lat=-23.5,
        base_lng=-46.6,
        current_lat=-23.5,
        current_lng=-46.6,
        degradation=0.0,
        breakdown_risk=0.0,
        status=TruckStatus.MAINTENANCE,
    )
    defaults.update(kwargs)
    return Truck(**defaults)


def make_engine():
    redis_client = AsyncMock()
    mock_session = AsyncMock()

    @asynccontextmanager
    async def session_factory():
        yield mock_session

    engine = SimulationEngine(redis_client, session_factory)
    return engine


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


def _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR):
    mock_truck_repo = AsyncMock()
    MTR.return_value = mock_truck_repo

    mock_store_repo = AsyncMock()
    MSR.return_value = mock_store_repo

    mock_factory_repo = AsyncMock()
    MFR.return_value = mock_factory_repo

    mock_order_repo = AsyncMock()
    MOR.return_value = mock_order_repo

    mock_route_repo = AsyncMock()
    mock_route_repo.get_active_by_truck.return_value = None
    MRR.return_value = mock_route_repo

    mock_event_repo = AsyncMock()
    MER.return_value = mock_event_repo

    mock_warehouse_repo = AsyncMock()
    MWR.return_value = mock_warehouse_repo

    return (
        mock_truck_repo, mock_store_repo, mock_factory_repo,
        mock_order_repo, mock_route_repo, mock_event_repo, mock_warehouse_repo,
    )


@pytest.mark.asyncio
async def test_completes_maintenance_after_duration():
    truck = make_truck(
        maintenance_start_tick=5,
        maintenance_duration_ticks=8,
    )
    world_state = make_world_state(trucks=[truck])

    engine = make_engine()
    engine._tick = 13

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR)
        mock_truck_repo = mocks[0]

        await engine._apply_physics(world_state)

    mock_truck_repo.update_status.assert_any_call("truck_01", "idle")
    mock_truck_repo.clear_maintenance_info.assert_called_once_with("truck_01")


@pytest.mark.asyncio
async def test_does_not_complete_maintenance_early():
    truck = make_truck(
        maintenance_start_tick=5,
        maintenance_duration_ticks=8,
    )
    world_state = make_world_state(trucks=[truck])

    engine = make_engine()
    engine._tick = 10

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR)
        mock_truck_repo = mocks[0]

        await engine._apply_physics(world_state)

    mock_truck_repo.update_status.assert_not_called()
    mock_truck_repo.clear_maintenance_info.assert_not_called()


@pytest.mark.asyncio
async def test_creates_maintenance_completed_event():
    truck = make_truck(
        maintenance_start_tick=5,
        maintenance_duration_ticks=8,
    )
    world_state = make_world_state(trucks=[truck])

    engine = make_engine()
    engine._tick = 13

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR)
        mock_event_repo = mocks[5]

        await engine._apply_physics(world_state)

    event_calls = mock_event_repo.create.call_args_list
    maintenance_calls = [
        c for c in event_calls
        if c[0][0].get("event_type") == "truck_maintenance_completed"
    ]
    assert len(maintenance_calls) == 1
    event_data = maintenance_calls[0][0][0]
    assert event_data["entity_type"] == "truck"
    assert event_data["entity_id"] == "truck_01"


@pytest.mark.asyncio
async def test_handles_legacy_maintenance_without_tracking():
    truck = make_truck(
        maintenance_start_tick=None,
        maintenance_duration_ticks=None,
    )
    world_state = make_world_state(trucks=[truck])

    engine = make_engine()
    engine._tick = 10

    patches = _patch_repos()
    with patches[0] as MTR, patches[1] as MSR, patches[2] as MFR, \
         patches[3] as MOR, patches[4] as MRR, patches[5] as MER, patches[6] as MWR:
        mocks = _setup_mocks(MTR, MSR, MFR, MOR, MRR, MER, MWR)
        mock_truck_repo = mocks[0]

        await engine._apply_physics(world_state)

    mock_truck_repo.update_status.assert_any_call("truck_01", "idle")
    mock_truck_repo.clear_maintenance_info.assert_called_once_with("truck_01")
