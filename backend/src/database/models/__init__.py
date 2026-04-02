from sqlalchemy import event
from sqlalchemy.orm import declarative_base

Base = declarative_base()


@event.listens_for(Base, "init", propagate=True)
def _apply_column_defaults(target, args, kwargs):
    for column_attr in target.__class__.__mapper__.column_attrs:
        col = column_attr.columns[0]
        if col.default is not None and not col.primary_key:
            attr_name = column_attr.key
            if attr_name not in kwargs:
                default = col.default
                if default.is_scalar:
                    setattr(target, attr_name, default.arg)
                elif callable(default.arg):
                    setattr(target, attr_name, default.arg(None))


from .material import Material
from .factory import Factory, FactoryProduct, FactoryPartnerWarehouse
from .warehouse import Warehouse, WarehouseStock
from .store import Store, StoreStock
from .truck import Truck
from .route import Route
from .order import PendingOrder
from .event import ChaosEvent
from .agent_decision import AgentDecision

__all__ = [
    "Base",
    "Material",
    "Factory",
    "FactoryProduct",
    "FactoryPartnerWarehouse",
    "Warehouse",
    "WarehouseStock",
    "Store",
    "StoreStock",
    "Truck",
    "Route",
    "PendingOrder",
    "ChaosEvent",
    "AgentDecision",
]
