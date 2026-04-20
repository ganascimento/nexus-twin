from unittest.mock import AsyncMock

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
async def test_stop_production_sets_rate_zero(processor):
    payload = {"material_id": "cimento"}

    await processor.process("factory", "factory_01", "stop_production", payload, current_tick=5)

    processor._factory_repo.update_production_rate.assert_called_once_with(
        "factory_01", "cimento", 0.0
    )
