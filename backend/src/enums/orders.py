import enum


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    IN_TRANSIT = "in_transit"
    REJECTED = "rejected"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class OrderRequesterType(str, enum.Enum):
    STORE = "store"
    WAREHOUSE = "warehouse"


class OrderTargetType(str, enum.Enum):
    WAREHOUSE = "warehouse"
    FACTORY = "factory"
