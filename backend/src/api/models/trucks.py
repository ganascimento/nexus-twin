from pydantic import BaseModel, ConfigDict


class TruckCreate(BaseModel):
    name: str
    truck_type: str
    lat: float
    lng: float


class TruckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    truck_type: str
    status: str
    degradation: float
    lat: float
    lng: float
