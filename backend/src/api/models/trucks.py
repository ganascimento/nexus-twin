from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TruckCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    truck_type: Literal["proprietario", "terceiro"]
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    factory_id: str | None = None
    capacity_tons: float = Field(gt=0)


class TruckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    truck_type: str
    capacity_tons: float
    status: str
    degradation: float
    current_lat: float
    current_lng: float
    factory_id: str | None = None
