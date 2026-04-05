import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from src.simulation.events import ROUTE_BLOCKED, SimulationEvent
from src.simulation.publisher import (
    publish_agent_decision,
    publish_event,
    publish_world_state,
)
from src.world.state import WorldState


def make_minimal_world_state():
    return WorldState(
        tick=1,
        simulated_timestamp=datetime(2024, 1, 1),
        materials=[],
        factories=[],
        warehouses=[],
        stores=[],
        trucks=[],
    )


def make_simulation_event():
    return SimulationEvent(
        event_type=ROUTE_BLOCKED,
        source="engine",
        entity_type="truck",
        entity_id="truck-001",
        payload={"detail": "accident"},
        tick=3,
    )


@pytest.mark.asyncio
async def test_publish_world_state_writes_to_correct_channel():
    redis_client = AsyncMock()
    world_state = make_minimal_world_state()

    await publish_world_state(world_state, tick=1, redis_client=redis_client)

    redis_client.publish.assert_called_once()
    channel, payload = redis_client.publish.call_args[0]
    assert channel == "nexus:world_state"
    parsed = json.loads(payload)
    assert parsed["tick"] == 1


@pytest.mark.asyncio
async def test_publish_agent_decision_writes_to_correct_channel():
    redis_client = AsyncMock()
    decision = {"agent": "warehouse", "action": "request_resupply", "quantity_tons": 50}

    await publish_agent_decision(decision, tick=2, redis_client=redis_client)

    redis_client.publish.assert_called_once()
    channel, payload = redis_client.publish.call_args[0]
    assert channel == "nexus:agent_decisions"
    parsed = json.loads(payload)
    assert parsed["action"] == "request_resupply"
    assert parsed["tick"] == 2


@pytest.mark.asyncio
async def test_publish_event_writes_to_correct_channel():
    redis_client = AsyncMock()
    event = make_simulation_event()

    await publish_event(event, redis_client=redis_client)

    redis_client.publish.assert_called_once()
    channel, payload = redis_client.publish.call_args[0]
    assert channel == "nexus:events"
    parsed = json.loads(payload)
    assert parsed["event_type"] == ROUTE_BLOCKED


@pytest.mark.asyncio
async def test_publisher_does_not_raise_on_redis_connection_error():
    redis_client = AsyncMock()
    redis_client.publish.side_effect = ConnectionError("Redis unavailable")
    world_state = make_minimal_world_state()

    # Must not raise — tick cannot stop due to publisher failure
    await publish_world_state(world_state, tick=1, redis_client=redis_client)
