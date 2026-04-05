from pydantic import BaseModel


class Material(BaseModel):
    id: str
    name: str
    is_active: bool
