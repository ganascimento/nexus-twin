from pydantic import BaseModel, ConfigDict


class WarehouseCreate(BaseModel):
    name: str
    lat: float
    lng: float
    region: str
    capacity_total: float


class WarehouseUpdate(BaseModel):
    name: str | None = None
    lat: float | None = None
    lng: float | None = None
    region: str | None = None
    capacity_total: float | None = None
    status: str | None = None


class WarehouseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    lat: float
    lng: float
    region: str
    capacity_total: float
    status: str
