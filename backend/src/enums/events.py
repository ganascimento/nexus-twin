import enum


class ChaosEventSource(str, enum.Enum):
    USER = "user"
    MASTER_AGENT = "master_agent"
    ENGINE = "engine"


class ChaosEventEntityType(str, enum.Enum):
    FACTORY = "factory"
    WAREHOUSE = "warehouse"
    STORE = "store"
    TRUCK = "truck"


class ChaosEventStatus(str, enum.Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
