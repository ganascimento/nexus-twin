from pydantic import BaseModel, Field


class StockAdjust(BaseModel):
    material_id: str = Field(min_length=1)
    delta: float
