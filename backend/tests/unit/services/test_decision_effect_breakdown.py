from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.enums import RouteNodeType
from src.services.decision_effect_processor import DecisionEffectProcessor
from src.world.entities.truck import TruckCargo


@pytest.fixture
def processor():
    return DecisionEffectProcessor(
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
async def test_alert_breakdown_dispatches_rescue(processor):
    broken_truck = MagicMock()
    broken_truck.id = "truck_broken"
    broken_truck.cargo = TruckCargo(
        material_id="cimento",
        quantity_tons=50,
        origin_type=RouteNodeType.FACTORY,
        origin_id="factory_01",
        destination_type=RouteNodeType.WAREHOUSE,
        destination_id="wh_01",
    )
    processor._truck_repo.get_by_id.return_value = broken_truck

    route = MagicMock()
    route.id = uuid4()
    route.origin_type = "factory"
    route.origin_id = "factory_01"
    route.dest_type = "warehouse"
    route.dest_id = "wh_01"
    route.order_id = uuid4()
    processor._route_repo.get_active_by_truck.return_value = route

    rescue_truck = MagicMock()
    rescue_truck.id = "truck_rescue"
    rescue_truck.truck_type = "terceiro"
    rescue_truck.status = "idle"
    processor._truck_repo.get_all.return_value = [rescue_truck]

    payload = {"current_degradation": 0.9}

    await processor.process("truck", "truck_broken", "alert_breakdown", payload, current_tick=10)

    processor._event_repo.create.assert_called_once()
    event_data = processor._event_repo.create.call_args[0][0]
    assert event_data["entity_type"] == "truck"
    assert event_data["entity_id"] == "truck_rescue"
    assert event_data["payload"]["rescue_for"] == "truck_broken"
    assert event_data["payload"]["material_id"] == "cimento"
    assert event_data["payload"]["quantity_tons"] == 50
    assert event_data["payload"]["destination_type"] == "warehouse"
    assert event_data["payload"]["destination_id"] == "wh_01"
