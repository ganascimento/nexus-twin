from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from src.guardrails.base import AgentDecisionBase


class StartProductionPayload(BaseModel):
    material_id: str
    quantity_tons: float

    @field_validator("quantity_tons")
    @classmethod
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("quantity_tons must be greater than 0")
        return v


class SendStockPayload(BaseModel):
    material_id: str
    quantity_tons: float
    destination_warehouse_id: str

    @field_validator("quantity_tons")
    @classmethod
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("quantity_tons must be greater than 0")
        return v


class FactoryDecision(AgentDecisionBase):
    action: Literal[
        "start_production", "reduce_production", "stop_production",
        "send_stock", "request_truck", "hold"
    ]
    payload: StartProductionPayload | SendStockPayload | None = None

    @model_validator(mode="after")
    def payload_required_for_actions(self):
        actions_requiring_payload = {"start_production", "send_stock"}
        if self.action in actions_requiring_payload and self.payload is None:
            raise ValueError(f"payload is required for action '{self.action}'")
        return self
