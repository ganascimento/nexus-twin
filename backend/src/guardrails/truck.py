from pydantic import BaseModel


class TruckDecision(BaseModel):
    action: str
    payload: dict = {}
    reasoning_summary: str = ""
