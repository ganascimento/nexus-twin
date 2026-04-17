from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from src.guardrails.base import AgentDecisionBase

MAINTENANCE_THRESHOLD = 0.30
DEGRADATION_BLOCK_THRESHOLD = 0.95


class AcceptContractPayload(BaseModel):
    order_id: str
    chosen_route_risk_level: Literal["low", "medium", "high"]


class RefuseContractPayload(BaseModel):
    order_id: str
    reason: Literal["high_degradation", "route_risk", "low_cargo_utilization", "in_maintenance"]


class RequestMaintenancePayload(BaseModel):
    current_degradation: float

    @field_validator("current_degradation")
    @classmethod
    def must_be_above_threshold(cls, v):
        if v < MAINTENANCE_THRESHOLD:
            raise ValueError(
                f"current_degradation ({v}) is below maintenance threshold ({MAINTENANCE_THRESHOLD})"
            )
        return v


class AlertBreakdownPayload(BaseModel):
    current_degradation: float
    route_id: str | None = None


class ReroutePayload(BaseModel):
    order_id: str
    reason: str


class TruckDecision(AgentDecisionBase):
    action: Literal[
        "accept_contract", "refuse_contract", "choose_route",
        "request_maintenance", "alert_breakdown", "complete_delivery",
        "reroute"
    ]
    payload: AcceptContractPayload | RefuseContractPayload | RequestMaintenancePayload | AlertBreakdownPayload | ReroutePayload | None = None
    degradation: float | None = None

    @model_validator(mode="after")
    def payload_required_for_actions(self):
        if self.action == "reroute" and self.payload is None:
            raise ValueError("payload is required for action 'reroute'")
        return self

    @model_validator(mode="after")
    def degradation_guardrail(self):
        if (
            self.degradation is not None
            and self.degradation >= DEGRADATION_BLOCK_THRESHOLD
            and self.action not in ("request_maintenance", "alert_breakdown")
        ):
            raise ValueError(
                f"degradation ({self.degradation}) >= {DEGRADATION_BLOCK_THRESHOLD}: "
                f"only 'request_maintenance' or 'alert_breakdown' is allowed"
            )
        return self
