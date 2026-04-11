from pydantic import BaseModel, ConfigDict, Field


class MaterialCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class MaterialUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class MaterialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    is_active: bool
