from __future__ import annotations

from typing import Dict

from pydantic import BaseModel

from src.enums import WarehouseStatus


class WarehouseStock(BaseModel):
    stock: float
    stock_reserved: float
    min_stock: float


class Warehouse(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    region: str
    capacity_total: float
    status: WarehouseStatus
    stocks: Dict[str, WarehouseStock]
