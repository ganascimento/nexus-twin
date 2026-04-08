from pydantic import BaseModel


class WarehouseDecision(BaseModel):
    action: str
    payload: dict = {}
    reasoning_summary: str = ""
