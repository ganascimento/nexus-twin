from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from src.guardrails.base import AgentDecisionBase


class OrderReplenishmentPayload(BaseModel):
    material_id: str
    quantity_tons: float
    from_warehouse_id: str

    @field_validator("quantity_tons")
    @classmethod
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("quantity_tons must be greater than 0")
        return v


class StoreDecision(AgentDecisionBase):
    action: Literal[
        "order_replenishment", "order_direct_from_factory",
        "wait_backoff", "hold"
    ]
    payload: OrderReplenishmentPayload | None = None

    @model_validator(mode="after")
    def payload_required_for_actions(self):
        if self.action == "order_replenishment" and self.payload is None:
            raise ValueError("payload is required for action 'order_replenishment'")
        return self
