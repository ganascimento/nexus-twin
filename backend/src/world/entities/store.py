from __future__ import annotations

from typing import Dict

from pydantic import BaseModel

from src.enums import StoreStatus


class StoreStock(BaseModel):
    stock: float
    demand_rate: float
    reorder_point: float


class Store(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    status: StoreStatus
    stocks: Dict[str, StoreStock]
