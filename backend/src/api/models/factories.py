from pydantic import BaseModel, ConfigDict


class FactoryCreate(BaseModel):
    name: str
    lat: float
    lng: float


class FactoryUpdate(BaseModel):
    name: str | None = None
    lat: float | None = None
    lng: float | None = None
    status: str | None = None


class FactoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    lat: float
    lng: float
    status: str
