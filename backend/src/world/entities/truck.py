from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from src.enums import RouteNodeType, TruckStatus, TruckType


class TruckCargo(BaseModel):
    material_id: str
    quantity_tons: float
    origin_type: RouteNodeType
    origin_id: str
    destination_type: RouteNodeType
    destination_id: str


class TruckRoute(BaseModel):
    route_id: str
    path: List[List[float]]
    timestamps: List[int]
    eta_ticks: int


class Truck(BaseModel):
    id: str
    truck_type: TruckType
    capacity_tons: float
    base_lat: float
    base_lng: float
    current_lat: float
    current_lng: float
    degradation: float
    breakdown_risk: float
    status: TruckStatus
    factory_id: Optional[str] = None
    cargo: Optional[TruckCargo] = None
    active_route: Optional[TruckRoute] = None
    maintenance_start_tick: Optional[int] = None
    maintenance_duration_ticks: Optional[int] = None
