import enum


class TruckType(str, enum.Enum):
    PROPRIETARIO = "proprietario"
    TERCEIRO = "terceiro"


class TruckStatus(str, enum.Enum):
    IDLE = "idle"
    EVALUATING = "evaluating"
    IN_TRANSIT = "in_transit"
    BROKEN = "broken"
    MAINTENANCE = "maintenance"
