from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel

from src.enums import FactoryStatus


class FactoryProduct(BaseModel):
    stock: float
    stock_reserved: float
    stock_max: float
    production_rate_max: float
    production_rate_current: float


class FactoryPartnerWarehouse(BaseModel):
    warehouse_id: str
    priority: int


class Factory(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    status: FactoryStatus
    products: Dict[str, FactoryProduct]
    partner_warehouses: List[FactoryPartnerWarehouse]
