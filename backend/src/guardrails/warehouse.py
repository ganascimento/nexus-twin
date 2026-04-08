from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from src.guardrails.base import AgentDecisionBase


class RequestResupplyPayload(BaseModel):
    material_id: str
    quantity_tons: float
    from_factory_id: str

    @field_validator("quantity_tons")
    @classmethod
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("quantity_tons must be greater than 0")
        return v


class ConfirmOrderPayload(BaseModel):
    order_id: str
    quantity_tons: float
    eta_ticks: int

    @field_validator("quantity_tons")
    @classmethod
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("quantity_tons must be greater than 0")
        return v

    @field_validator("eta_ticks")
    @classmethod
    def eta_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("eta_ticks must be greater than 0")
        return v


class RejectOrderPayload(BaseModel):
    order_id: str
    reason: str
    retry_after_ticks: int

    @field_validator("retry_after_ticks")
    @classmethod
    def must_be_non_negative(cls, v):
        if v < 0:
            raise ValueError("retry_after_ticks must be >= 0")
        return v


class WarehouseDecision(AgentDecisionBase):
    action: Literal[
        "request_resupply", "confirm_order", "reject_order",
        "request_delivery_truck", "ration_stock", "hold"
    ]
    payload: RequestResupplyPayload | ConfirmOrderPayload | RejectOrderPayload | None = None

    @model_validator(mode="after")
    def payload_required_for_actions(self):
        actions_requiring_payload = {"request_resupply", "confirm_order", "reject_order"}
        if self.action in actions_requiring_payload and self.payload is None:
            raise ValueError(f"payload is required for action '{self.action}'")
        return self
