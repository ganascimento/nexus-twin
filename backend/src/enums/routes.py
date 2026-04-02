import enum


class RouteNodeType(str, enum.Enum):
    FACTORY = "factory"
    WAREHOUSE = "warehouse"
    STORE = "store"


class RouteStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
