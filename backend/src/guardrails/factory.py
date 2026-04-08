from pydantic import BaseModel


class FactoryDecision(BaseModel):
    action: str
    payload: dict = {}
    reasoning_summary: str = ""
