from pydantic import BaseModel


class StockAdjust(BaseModel):
    material_id: str
    delta: float
