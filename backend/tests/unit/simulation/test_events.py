from src.simulation.events import (
    LOW_STOCK_TRIGGER,
    MACHINE_BREAKDOWN,
    ROUTE_BLOCKED,
    SimulationEvent,
    chaos_event,
    route_event,
    trigger_event,
)


def test_simulation_event_factory_functions_produce_correct_fields():
    re = route_event(
        event_type=ROUTE_BLOCKED,
        entity_id="truck-001",
        payload={"segment": "sp-330"},
        tick=5,
    )
    assert isinstance(re, SimulationEvent)
    assert re.event_type == ROUTE_BLOCKED
    assert re.entity_id == "truck-001"
    assert re.payload == {"segment": "sp-330"}
    assert re.tick == 5
    assert re.entity_type == "truck"
    assert re.source == "engine"

    te = trigger_event(
        entity_type="store",
        entity_id="store-001",
        event_type=LOW_STOCK_TRIGGER,
        tick=10,
    )
    assert isinstance(te, SimulationEvent)
    assert te.event_type == LOW_STOCK_TRIGGER
    assert te.entity_type == "store"
    assert te.entity_id == "store-001"
    assert te.tick == 10
    assert te.payload == {}

    ce = chaos_event(
        event_type=MACHINE_BREAKDOWN,
        source="master_agent",
        entity_type="factory",
        entity_id="f-001",
        payload={"severity": "high"},
        tick=20,
    )
    assert isinstance(ce, SimulationEvent)
    assert ce.event_type == MACHINE_BREAKDOWN
    assert ce.source == "master_agent"
    assert ce.entity_type == "factory"
    assert ce.entity_id == "f-001"
    assert ce.payload == {"severity": "high"}
    assert ce.tick == 20
