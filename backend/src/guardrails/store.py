from pydantic import BaseModel


class StoreDecision(BaseModel):
    action: str
    payload: dict = {}
    reasoning_summary: str = ""
