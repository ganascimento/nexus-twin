from src.enums import (
    AgentType,
    TruckType,
    TruckStatus,
    FactoryStatus,
    WarehouseStatus,
    StoreStatus,
    RouteNodeType,
    RouteStatus,
    ChaosEventSource,
    ChaosEventEntityType,
    ChaosEventStatus,
    OrderStatus,
    OrderRequesterType,
    OrderTargetType,
)


def test_agent_type_values():
    assert AgentType.FACTORY.value == "factory"
    assert AgentType.WAREHOUSE.value == "warehouse"
    assert AgentType.STORE.value == "store"
    assert AgentType.TRUCK.value == "truck"
    assert AgentType.MASTER.value == "master"


def test_agent_type_member_count():
    assert len(AgentType) == 5


def test_truck_type_values():
    assert TruckType.PROPRIETARIO.value == "proprietario"
    assert TruckType.TERCEIRO.value == "terceiro"


def test_truck_type_member_count():
    assert len(TruckType) == 2


def test_truck_status_values():
    assert TruckStatus.IDLE.value == "idle"
    assert TruckStatus.EVALUATING.value == "evaluating"
    assert TruckStatus.IN_TRANSIT.value == "in_transit"
    assert TruckStatus.BROKEN.value == "broken"
    assert TruckStatus.MAINTENANCE.value == "maintenance"


def test_truck_status_member_count():
    assert len(TruckStatus) == 5


def test_factory_status_values():
    assert FactoryStatus.OPERATING.value == "operating"
    assert FactoryStatus.STOPPED.value == "stopped"
    assert FactoryStatus.REDUCED_CAPACITY.value == "reduced_capacity"


def test_factory_status_member_count():
    assert len(FactoryStatus) == 3


def test_warehouse_status_values():
    assert WarehouseStatus.OPERATING.value == "operating"
    assert WarehouseStatus.RATIONING.value == "rationing"
    assert WarehouseStatus.OFFLINE.value == "offline"


def test_warehouse_status_member_count():
    assert len(WarehouseStatus) == 3


def test_store_status_values():
    assert StoreStatus.OPEN.value == "open"
    assert StoreStatus.DEMAND_PAUSED.value == "demand_paused"
    assert StoreStatus.OFFLINE.value == "offline"


def test_store_status_member_count():
    assert len(StoreStatus) == 3


def test_route_node_type_values():
    assert RouteNodeType.FACTORY.value == "factory"
    assert RouteNodeType.WAREHOUSE.value == "warehouse"
    assert RouteNodeType.STORE.value == "store"


def test_route_node_type_member_count():
    assert len(RouteNodeType) == 3


def test_route_status_values():
    assert RouteStatus.ACTIVE.value == "active"
    assert RouteStatus.COMPLETED.value == "completed"
    assert RouteStatus.INTERRUPTED.value == "interrupted"


def test_route_status_member_count():
    assert len(RouteStatus) == 3


def test_chaos_event_source_values():
    assert ChaosEventSource.USER.value == "user"
    assert ChaosEventSource.MASTER_AGENT.value == "master_agent"
    assert ChaosEventSource.ENGINE.value == "engine"


def test_chaos_event_source_member_count():
    assert len(ChaosEventSource) == 3


def test_chaos_event_entity_type_values():
    assert ChaosEventEntityType.FACTORY.value == "factory"
    assert ChaosEventEntityType.WAREHOUSE.value == "warehouse"
    assert ChaosEventEntityType.STORE.value == "store"
    assert ChaosEventEntityType.TRUCK.value == "truck"


def test_chaos_event_entity_type_member_count():
    assert len(ChaosEventEntityType) == 4


def test_chaos_event_status_values():
    assert ChaosEventStatus.ACTIVE.value == "active"
    assert ChaosEventStatus.RESOLVED.value == "resolved"


def test_chaos_event_status_member_count():
    assert len(ChaosEventStatus) == 2


def test_order_status_values():
    assert OrderStatus.PENDING.value == "pending"
    assert OrderStatus.CONFIRMED.value == "confirmed"
    assert OrderStatus.REJECTED.value == "rejected"
    assert OrderStatus.DELIVERED.value == "delivered"
    assert OrderStatus.CANCELLED.value == "cancelled"


def test_order_status_member_count():
    assert len(OrderStatus) == 5


def test_order_requester_type_values():
    assert OrderRequesterType.STORE.value == "store"
    assert OrderRequesterType.WAREHOUSE.value == "warehouse"


def test_order_requester_type_member_count():
    assert len(OrderRequesterType) == 2


def test_order_target_type_values():
    assert OrderTargetType.WAREHOUSE.value == "warehouse"
    assert OrderTargetType.FACTORY.value == "factory"


def test_order_target_type_member_count():
    assert len(OrderTargetType) == 2
