import pytest
from pydantic import ValidationError

from src.guardrails.store import (
    OrderReplenishmentPayload,
    StoreDecision,
)


class TestOrderReplenishmentPayload:
    def test_valid(self):
        payload = OrderReplenishmentPayload(
            material_id="mat_1", quantity_tons=10.0, from_warehouse_id="wh_1"
        )
        assert payload.from_warehouse_id == "wh_1"

    def test_zero_quantity_rejected(self):
        with pytest.raises(ValidationError):
            OrderReplenishmentPayload(
                material_id="mat_1", quantity_tons=0, from_warehouse_id="wh_1"
            )

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValidationError):
            OrderReplenishmentPayload(
                material_id="mat_1", quantity_tons=-3.0, from_warehouse_id="wh_1"
            )


class TestStoreDecision:
    def test_order_replenishment_with_payload(self):
        decision = StoreDecision(
            action="order_replenishment",
            reasoning_summary="Stock below reorder point",
            payload=OrderReplenishmentPayload(
                material_id="mat_1", quantity_tons=20.0, from_warehouse_id="wh_1"
            ),
        )
        assert decision.action == "order_replenishment"

    def test_order_direct_from_factory_without_payload(self):
        decision = StoreDecision(
            action="order_direct_from_factory",
            reasoning_summary="Warehouse unavailable",
        )
        assert decision.payload is None

    def test_wait_backoff_without_payload(self):
        decision = StoreDecision(
            action="wait_backoff",
            reasoning_summary="Recent order pending",
        )
        assert decision.payload is None

    def test_hold_without_payload(self):
        decision = StoreDecision(
            action="hold",
            reasoning_summary="Stock adequate",
        )
        assert decision.payload is None

    def test_invalid_action_rejected(self):
        with pytest.raises(ValidationError):
            StoreDecision(
                action="invalid_action",
                reasoning_summary="Test",
            )

    def test_order_replenishment_without_payload_rejected(self):
        with pytest.raises(ValidationError):
            StoreDecision(
                action="order_replenishment",
                reasoning_summary="Missing payload",
            )
