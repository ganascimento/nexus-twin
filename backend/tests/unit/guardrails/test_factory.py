import pytest
from pydantic import ValidationError

from src.guardrails.factory import (
    FactoryDecision,
    SendStockPayload,
    StartProductionPayload,
)


class TestStartProductionPayload:
    def test_valid(self):
        payload = StartProductionPayload(material_id="mat_1", quantity_tons=10.0)
        assert payload.material_id == "mat_1"
        assert payload.quantity_tons == 10.0

    def test_zero_quantity_rejected(self):
        with pytest.raises(ValidationError):
            StartProductionPayload(material_id="mat_1", quantity_tons=0)

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValidationError):
            StartProductionPayload(material_id="mat_1", quantity_tons=-5.0)


class TestSendStockPayload:
    def test_valid(self):
        payload = SendStockPayload(
            material_id="mat_1",
            quantity_tons=20.0,
            destination_warehouse_id="wh_1",
        )
        assert payload.destination_warehouse_id == "wh_1"

    def test_zero_quantity_rejected(self):
        with pytest.raises(ValidationError):
            SendStockPayload(
                material_id="mat_1",
                quantity_tons=0,
                destination_warehouse_id="wh_1",
            )

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValidationError):
            SendStockPayload(
                material_id="mat_1",
                quantity_tons=-1.0,
                destination_warehouse_id="wh_1",
            )


class TestFactoryDecision:
    def test_start_production_with_payload(self):
        decision = FactoryDecision(
            action="start_production",
            reasoning_summary="Demand is high",
            payload=StartProductionPayload(material_id="mat_1", quantity_tons=50.0),
        )
        assert decision.action == "start_production"
        assert isinstance(decision.payload, StartProductionPayload)

    def test_send_stock_with_payload(self):
        decision = FactoryDecision(
            action="send_stock",
            reasoning_summary="Warehouse running low",
            payload=SendStockPayload(
                material_id="mat_1",
                quantity_tons=30.0,
                destination_warehouse_id="wh_1",
            ),
        )
        assert decision.action == "send_stock"

    def test_reduce_production_without_payload(self):
        decision = FactoryDecision(
            action="reduce_production",
            reasoning_summary="Demand dropped",
        )
        assert decision.payload is None

    def test_stop_production_without_payload(self):
        decision = FactoryDecision(
            action="stop_production",
            reasoning_summary="Maintenance scheduled",
        )
        assert decision.payload is None

    def test_stop_production_with_material_id_payload(self):
        decision = FactoryDecision(
            action="stop_production",
            reasoning_summary="Machine breakdown",
            payload={"material_id": "cimento"},
        )
        assert decision.payload is not None
        assert decision.payload.material_id == "cimento"

    def test_request_truck_without_payload(self):
        decision = FactoryDecision(
            action="request_truck",
            reasoning_summary="Need transport",
        )
        assert decision.payload is None

    def test_hold_without_payload(self):
        decision = FactoryDecision(
            action="hold",
            reasoning_summary="All good",
        )
        assert decision.payload is None

    def test_invalid_action_rejected(self):
        with pytest.raises(ValidationError):
            FactoryDecision(
                action="invalid_action",
                reasoning_summary="Test",
            )

    def test_start_production_without_payload_rejected(self):
        with pytest.raises(ValidationError):
            FactoryDecision(
                action="start_production",
                reasoning_summary="Missing payload",
            )

    def test_send_stock_without_payload_rejected(self):
        with pytest.raises(ValidationError):
            FactoryDecision(
                action="send_stock",
                reasoning_summary="Missing payload",
            )
