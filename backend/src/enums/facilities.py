import enum


class FactoryStatus(str, enum.Enum):
    OPERATING = "operating"
    STOPPED = "stopped"
    REDUCED_CAPACITY = "reduced_capacity"


class WarehouseStatus(str, enum.Enum):
    OPERATING = "operating"
    RATIONING = "rationing"
    OFFLINE = "offline"


class StoreStatus(str, enum.Enum):
    OPEN = "open"
    DEMAND_PAUSED = "demand_paused"
    OFFLINE = "offline"
