from pydantic import BaseModel, ConfigDict


class StoreCreate(BaseModel):
    name: str
    lat: float
    lng: float
    region: str


class StoreUpdate(BaseModel):
    name: str | None = None
    lat: float | None = None
    lng: float | None = None
    region: str | None = None
    status: str | None = None


class StoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    lat: float
    lng: float
    status: str
    region: str
