import json
from dataclasses import asdict

from loguru import logger

from src.simulation.events import SimulationEvent
from src.world.state import WorldState


async def publish_world_state(
    world_state: WorldState,
    tick: int,
    redis_client,
    active_routes: list[dict] | None = None,
) -> None:
    try:
        payload = world_state.model_dump(mode="json")
        payload["tick"] = tick
        payload.setdefault("active_events", [])
        payload["active_routes"] = active_routes or []
        await redis_client.publish("nexus:world_state", json.dumps(payload))
    except Exception as exc:
        logger.error(f"Failed to publish world state to Redis: {exc}")


async def publish_agent_decision(decision: dict, tick: int, redis_client) -> None:
    try:
        payload = {**decision, "tick": tick}
        await redis_client.publish("nexus:agent_decisions", json.dumps(payload))
    except Exception as exc:
        logger.error(f"Failed to publish agent decision to Redis: {exc}")


async def publish_event(event: SimulationEvent, redis_client) -> None:
    try:
        await redis_client.publish("nexus:events", json.dumps(asdict(event)))
    except Exception as exc:
        logger.error(f"Failed to publish simulation event to Redis: {exc}")
