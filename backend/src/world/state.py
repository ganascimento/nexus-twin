from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict

from src.world.entities.factory import Factory
from src.world.entities.material import Material
from src.world.entities.store import Store
from src.world.entities.truck import Truck
from src.world.entities.warehouse import Warehouse


class WorldState(BaseModel):
    model_config = ConfigDict(frozen=True)

    tick: int
    simulated_timestamp: datetime
    materials: List[Material]
    factories: List[Factory]
    warehouses: List[Warehouse]
    stores: List[Store]
    trucks: List[Truck]
