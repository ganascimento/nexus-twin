from dataclasses import dataclass
from typing import Optional

ROUTE_BLOCKED = "route_blocked"
TRUCK_ARRIVED = "truck_arrived"
TRUCK_BREAKDOWN = "truck_breakdown"
NEW_ORDER = "new_order"
CONTRACT_PROPOSAL = "contract_proposal"
MACHINE_BREAKDOWN = "machine_breakdown"
DEMAND_SPIKE = "demand_spike"
STRIKE = "strike"
STORM = "storm"
SUDDEN_DEMAND_ZERO = "sudden_demand_zero"
ENGINE_BLOCKED_DEGRADED_TRUCK = "engine_blocked_degraded_truck"
LOW_STOCK_TRIGGER = "low_stock_trigger"
STOCK_TRIGGER_WAREHOUSE = "stock_trigger_warehouse"
STOCK_TRIGGER_FACTORY = "stock_trigger_factory"
ORDER_RECEIVED = "order_received"
RESUPPLY_REQUESTED = "resupply_requested"

TRUCK_AGENT_EVENT_TYPES = frozenset(
    {ROUTE_BLOCKED, TRUCK_ARRIVED, TRUCK_BREAKDOWN, NEW_ORDER, CONTRACT_PROPOSAL}
)


@dataclass
class SimulationEvent:
    event_type: str
    source: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    payload: dict
    tick: int


def route_event(
    event_type: str, entity_id: str, payload: dict, tick: int
) -> SimulationEvent:
    return SimulationEvent(
        event_type=event_type,
        source="engine",
        entity_type="truck",
        entity_id=entity_id,
        payload=payload,
        tick=tick,
    )


def trigger_event(
    entity_type: str,
    entity_id: str,
    event_type: str,
    tick: int,
    payload: dict | None = None,
) -> SimulationEvent:
    return SimulationEvent(
        event_type=event_type,
        source="engine",
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
        tick=tick,
    )


def chaos_event(
    event_type: str,
    source: str,
    entity_type: Optional[str],
    entity_id: Optional[str],
    payload: dict,
    tick: int,
) -> SimulationEvent:
    return SimulationEvent(
        event_type=event_type,
        source=source,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        tick=tick,
    )
