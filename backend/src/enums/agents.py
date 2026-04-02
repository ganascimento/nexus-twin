import enum


class AgentType(str, enum.Enum):
    FACTORY = "factory"
    WAREHOUSE = "warehouse"
    STORE = "store"
    TRUCK = "truck"
    MASTER = "master"
