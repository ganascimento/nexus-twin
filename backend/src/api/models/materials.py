from pydantic import BaseModel, ConfigDict


class MaterialCreate(BaseModel):
    name: str


class MaterialUpdate(BaseModel):
    name: str


class MaterialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    is_active: bool
