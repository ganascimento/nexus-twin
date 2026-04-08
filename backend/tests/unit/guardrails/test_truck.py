import pytest
from pydantic import ValidationError

from src.guardrails.truck import (
    AcceptContractPayload,
    RefuseContractPayload,
    RequestMaintenancePayload,
    TruckDecision,
)


class TestAcceptContractPayload:
    def test_valid(self):
        payload = AcceptContractPayload(
            order_id="ord_1", chosen_route_risk_level="low"
        )
        assert payload.chosen_route_risk_level == "low"

    def test_medium_risk(self):
        payload = AcceptContractPayload(
            order_id="ord_1", chosen_route_risk_level="medium"
        )
        assert payload.chosen_route_risk_level == "medium"

    def test_high_risk(self):
        payload = AcceptContractPayload(
            order_id="ord_1", chosen_route_risk_level="high"
        )
        assert payload.chosen_route_risk_level == "high"

    def test_invalid_risk_level_rejected(self):
        with pytest.raises(ValidationError):
            AcceptContractPayload(
                order_id="ord_1", chosen_route_risk_level="extreme"
            )


class TestRefuseContractPayload:
    def test_valid_high_degradation(self):
        payload = RefuseContractPayload(
            order_id="ord_1", reason="high_degradation"
        )
        assert payload.reason == "high_degradation"

    def test_valid_route_risk(self):
        payload = RefuseContractPayload(order_id="ord_1", reason="route_risk")
        assert payload.reason == "route_risk"

    def test_valid_low_cargo(self):
        payload = RefuseContractPayload(
            order_id="ord_1", reason="low_cargo_utilization"
        )
        assert payload.reason == "low_cargo_utilization"

    def test_valid_in_maintenance(self):
        payload = RefuseContractPayload(
            order_id="ord_1", reason="in_maintenance"
        )
        assert payload.reason == "in_maintenance"

    def test_invalid_reason_rejected(self):
        with pytest.raises(ValidationError):
            RefuseContractPayload(order_id="ord_1", reason="too_tired")


class TestRequestMaintenancePayload:
    def test_valid_above_threshold(self):
        payload = RequestMaintenancePayload(current_degradation=0.5)
        assert payload.current_degradation == 0.5

    def test_at_threshold(self):
        payload = RequestMaintenancePayload(current_degradation=0.3)
        assert payload.current_degradation == 0.3

    def test_below_threshold_rejected(self):
        with pytest.raises(ValidationError):
            RequestMaintenancePayload(current_degradation=0.1)

    def test_zero_degradation_rejected(self):
        with pytest.raises(ValidationError):
            RequestMaintenancePayload(current_degradation=0.0)


class TestTruckDecision:
    def test_accept_contract(self):
        decision = TruckDecision(
            action="accept_contract",
            reasoning_summary="Good route and cargo",
            payload=AcceptContractPayload(
                order_id="ord_1", chosen_route_risk_level="low"
            ),
        )
        assert decision.action == "accept_contract"

    def test_refuse_contract(self):
        decision = TruckDecision(
            action="refuse_contract",
            reasoning_summary="Route too risky",
            payload=RefuseContractPayload(
                order_id="ord_1", reason="route_risk"
            ),
        )
        assert decision.action == "refuse_contract"

    def test_choose_route_without_payload(self):
        decision = TruckDecision(
            action="choose_route",
            reasoning_summary="Selecting optimal route",
        )
        assert decision.payload is None

    def test_request_maintenance(self):
        decision = TruckDecision(
            action="request_maintenance",
            reasoning_summary="Degradation high",
            payload=RequestMaintenancePayload(current_degradation=0.75),
        )
        assert decision.action == "request_maintenance"

    def test_alert_breakdown_without_payload(self):
        decision = TruckDecision(
            action="alert_breakdown",
            reasoning_summary="Truck broke down",
        )
        assert decision.payload is None

    def test_complete_delivery_without_payload(self):
        decision = TruckDecision(
            action="complete_delivery",
            reasoning_summary="Delivery finished",
        )
        assert decision.payload is None

    def test_invalid_action_rejected(self):
        with pytest.raises(ValidationError):
            TruckDecision(
                action="fly_away",
                reasoning_summary="Test",
            )

    def test_degradation_block_rejects_non_maintenance_action(self):
        with pytest.raises(ValidationError):
            TruckDecision(
                action="accept_contract",
                reasoning_summary="Trying to accept despite critical degradation",
                degradation=0.95,
                payload=AcceptContractPayload(
                    order_id="ord_1", chosen_route_risk_level="low"
                ),
            )

    def test_degradation_block_rejects_at_100_percent(self):
        with pytest.raises(ValidationError):
            TruckDecision(
                action="complete_delivery",
                reasoning_summary="Trying to deliver at max degradation",
                degradation=1.0,
            )

    def test_degradation_block_allows_request_maintenance(self):
        decision = TruckDecision(
            action="request_maintenance",
            reasoning_summary="Critical degradation, must repair",
            degradation=0.95,
            payload=RequestMaintenancePayload(current_degradation=0.95),
        )
        assert decision.action == "request_maintenance"

    def test_below_degradation_threshold_allows_any_action(self):
        decision = TruckDecision(
            action="accept_contract",
            reasoning_summary="Degradation is fine",
            degradation=0.5,
            payload=AcceptContractPayload(
                order_id="ord_1", chosen_route_risk_level="medium"
            ),
        )
        assert decision.action == "accept_contract"
