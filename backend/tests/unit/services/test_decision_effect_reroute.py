from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.services.decision_effect_processor import DecisionEffectProcessor


@pytest.fixture
def processor():
    return DecisionEffectProcessor(
        session=AsyncMock(),
        order_repo=AsyncMock(),
        warehouse_service=AsyncMock(),
        factory_repo=AsyncMock(),
        truck_service=AsyncMock(),
        route_service=AsyncMock(),
        event_repo=AsyncMock(),
        truck_repo=AsyncMock(),
        warehouse_repo=AsyncMock(),
        store_repo=AsyncMock(),
        route_repo=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_handle_reroute_computes_new_route(processor):
    truck = MagicMock()
    truck.id = "truck_01"
    truck.current_lat = -23.5
    truck.current_lng = -46.6
    processor._truck_repo.get_by_id.return_value = truck

    route = MagicMock()
    route.id = uuid4()
    route.dest_type = "warehouse"
    route.dest_id = "wh_01"

    processor._route_repo = AsyncMock()
    processor._route_repo.get_active_by_truck = AsyncMock(return_value=route)

    warehouse = MagicMock()
    warehouse.lat = -22.8
    warehouse.lng = -45.8
    processor._warehouse_repo.get_by_id.return_value = warehouse

    new_route_data = {
        "path": [[-46.6, -23.5], [-45.8, -22.8]],
        "timestamps": [5, 10],
        "eta_ticks": 5,
    }
    processor._route_service.compute_route.return_value = new_route_data

    payload = {"order_id": "order_01", "reason": "route_blocked"}

    await processor.process("truck", "truck_01", "reroute", payload, current_tick=5)

    processor._route_service.compute_route.assert_called_once_with(
        -23.5, -46.6, -22.8, -45.8, 5,
    )


@pytest.mark.asyncio
async def test_handle_reroute_updates_active_route(processor):
    truck = MagicMock()
    truck.id = "truck_01"
    truck.current_lat = -23.5
    truck.current_lng = -46.6
    processor._truck_repo.get_by_id.return_value = truck

    route_id = uuid4()
    route = MagicMock()
    route.id = route_id
    route.dest_type = "warehouse"
    route.dest_id = "wh_01"

    processor._route_repo = AsyncMock()
    processor._route_repo.get_active_by_truck = AsyncMock(return_value=route)

    warehouse = MagicMock()
    warehouse.lat = -22.8
    warehouse.lng = -45.8
    processor._warehouse_repo.get_by_id.return_value = warehouse

    new_route_data = {
        "path": [[-46.6, -23.5], [-45.8, -22.8]],
        "timestamps": [5, 10],
        "eta_ticks": 5,
    }
    processor._route_service.compute_route.return_value = new_route_data

    payload = {"order_id": "order_01", "reason": "route_blocked"}

    await processor.process("truck", "truck_01", "reroute", payload, current_tick=5)

    processor._route_repo.update_route_data.assert_called_once_with(
        route_id,
        [[-46.6, -23.5], [-45.8, -22.8]],
        [5, 10],
        5,
    )
