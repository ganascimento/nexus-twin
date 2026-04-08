import pytest
from pydantic import ValidationError

from src.guardrails.warehouse import (
    ConfirmOrderPayload,
    RejectOrderPayload,
    RequestResupplyPayload,
    WarehouseDecision,
)


class TestRequestResupplyPayload:
    def test_valid(self):
        payload = RequestResupplyPayload(
            material_id="mat_1", quantity_tons=25.0, from_factory_id="fac_1"
        )
        assert payload.from_factory_id == "fac_1"

    def test_zero_quantity_rejected(self):
        with pytest.raises(ValidationError):
            RequestResupplyPayload(
                material_id="mat_1", quantity_tons=0, from_factory_id="fac_1"
            )

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValidationError):
            RequestResupplyPayload(
                material_id="mat_1", quantity_tons=-10.0, from_factory_id="fac_1"
            )


class TestConfirmOrderPayload:
    def test_valid(self):
        payload = ConfirmOrderPayload(
            order_id="ord_1", quantity_tons=15.0, eta_ticks=3
        )
        assert payload.eta_ticks == 3

    def test_zero_quantity_rejected(self):
        with pytest.raises(ValidationError):
            ConfirmOrderPayload(order_id="ord_1", quantity_tons=0, eta_ticks=3)

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValidationError):
            ConfirmOrderPayload(order_id="ord_1", quantity_tons=-5.0, eta_ticks=3)

    def test_zero_eta_ticks_rejected(self):
        with pytest.raises(ValidationError):
            ConfirmOrderPayload(order_id="ord_1", quantity_tons=10.0, eta_ticks=0)

    def test_negative_eta_ticks_rejected(self):
        with pytest.raises(ValidationError):
            ConfirmOrderPayload(order_id="ord_1", quantity_tons=10.0, eta_ticks=-1)


class TestRejectOrderPayload:
    def test_valid(self):
        payload = RejectOrderPayload(
            order_id="ord_1", reason="Out of stock", retry_after_ticks=5
        )
        assert payload.reason == "Out of stock"

    def test_zero_retry_after_ticks_accepted(self):
        payload = RejectOrderPayload(
            order_id="ord_1", reason="No capacity", retry_after_ticks=0
        )
        assert payload.retry_after_ticks == 0

    def test_negative_retry_after_ticks_rejected(self):
        with pytest.raises(ValidationError):
            RejectOrderPayload(
                order_id="ord_1", reason="No capacity", retry_after_ticks=-1
            )


class TestWarehouseDecision:
    def test_request_resupply_with_payload(self):
        decision = WarehouseDecision(
            action="request_resupply",
            reasoning_summary="Stock projected to run out",
            payload=RequestResupplyPayload(
                material_id="mat_1", quantity_tons=50.0, from_factory_id="fac_1"
            ),
        )
        assert decision.action == "request_resupply"

    def test_confirm_order_with_payload(self):
        decision = WarehouseDecision(
            action="confirm_order",
            reasoning_summary="Order fulfilled",
            payload=ConfirmOrderPayload(
                order_id="ord_1", quantity_tons=20.0, eta_ticks=2
            ),
        )
        assert isinstance(decision.payload, ConfirmOrderPayload)

    def test_reject_order_with_payload(self):
        decision = WarehouseDecision(
            action="reject_order",
            reasoning_summary="Cannot fulfill",
            payload=RejectOrderPayload(
                order_id="ord_1", reason="No stock", retry_after_ticks=10
            ),
        )
        assert isinstance(decision.payload, RejectOrderPayload)

    def test_request_delivery_truck_without_payload(self):
        decision = WarehouseDecision(
            action="request_delivery_truck",
            reasoning_summary="Need truck for delivery",
        )
        assert decision.payload is None

    def test_ration_stock_without_payload(self):
        decision = WarehouseDecision(
            action="ration_stock",
            reasoning_summary="Low stock, rationing",
        )
        assert decision.payload is None

    def test_hold_without_payload(self):
        decision = WarehouseDecision(
            action="hold",
            reasoning_summary="Stable state",
        )
        assert decision.payload is None

    def test_invalid_action_rejected(self):
        with pytest.raises(ValidationError):
            WarehouseDecision(
                action="invalid_action",
                reasoning_summary="Test",
            )

    def test_request_resupply_without_payload_rejected(self):
        with pytest.raises(ValidationError):
            WarehouseDecision(
                action="request_resupply",
                reasoning_summary="Missing payload",
            )

    def test_confirm_order_without_payload_rejected(self):
        with pytest.raises(ValidationError):
            WarehouseDecision(
                action="confirm_order",
                reasoning_summary="Missing payload",
            )

    def test_reject_order_without_payload_rejected(self):
        with pytest.raises(ValidationError):
            WarehouseDecision(
                action="reject_order",
                reasoning_summary="Missing payload",
            )
