from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from src.workers.tasks.exports import (
    export_decision_history,
    export_event_history,
    export_world_snapshot,
)


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


class TestExportDecisionHistory:
    @patch("src.workers.tasks.exports.get_sync_session")
    def test_returns_list_of_dicts_with_expected_fields(
        self, mock_get_session, mock_session
    ):
        mock_get_session.return_value = mock_session

        decision = MagicMock()
        decision.tick = 10
        decision.agent_type = "factory"
        decision.entity_id = "factory_01"
        decision.action = "start_production"
        decision.reasoning = "low stock detected"
        decision.created_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [decision]
        mock_session.execute.return_value = result_mock

        result = export_decision_history()

        assert len(result) == 1
        assert result[0]["tick"] == 10
        assert result[0]["agent_type"] == "factory"
        assert result[0]["entity_id"] == "factory_01"
        assert result[0]["action"] == "start_production"
        assert result[0]["reasoning_summary"] == "low stock detected"
        assert "created_at" in result[0]

    @patch("src.workers.tasks.exports.get_sync_session")
    def test_filter_by_entity_id(self, mock_get_session, mock_session):
        mock_get_session.return_value = mock_session

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = result_mock

        export_decision_history(entity_id="factory_01")

        mock_session.execute.assert_called_once()

    @patch("src.workers.tasks.exports.get_sync_session")
    def test_limit_parameter(self, mock_get_session, mock_session):
        mock_get_session.return_value = mock_session

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = result_mock

        export_decision_history(limit=10)

        mock_session.execute.assert_called_once()

    @patch("src.workers.tasks.exports.get_sync_session")
    def test_empty_result(self, mock_get_session, mock_session):
        mock_get_session.return_value = mock_session

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = result_mock

        result = export_decision_history()

        assert result == []


class TestExportEventHistory:
    @patch("src.workers.tasks.exports.get_sync_session")
    def test_returns_list_with_expected_fields(self, mock_get_session, mock_session):
        mock_get_session.return_value = mock_session

        event = MagicMock()
        event.id = "evt_01"
        event.event_type = "route_blocked"
        event.source = "user"
        event.entity_type = "truck"
        event.entity_id = "truck_01"
        event.status = "resolved"
        event.tick_start = 5
        event.tick_end = 10
        event.created_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [event]
        mock_session.execute.return_value = result_mock

        result = export_event_history()

        assert len(result) == 1
        assert result[0]["event_type"] == "route_blocked"
        assert result[0]["status"] == "resolved"
        assert result[0]["tick_start"] == 5
        assert result[0]["tick_end"] == 10
        assert result[0]["entity_type"] == "truck"
        assert result[0]["entity_id"] == "truck_01"

    @patch("src.workers.tasks.exports.get_sync_session")
    def test_empty_events(self, mock_get_session, mock_session):
        mock_get_session.return_value = mock_session

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = result_mock

        result = export_event_history()

        assert result == []


class TestExportWorldSnapshot:
    @patch("src.workers.tasks.exports.get_sync_session")
    def test_returns_dict_with_all_entity_types(self, mock_get_session, mock_session):
        mock_get_session.return_value = mock_session

        factory = MagicMock()
        factory.id = "f1"
        factory.name = "Campinas Factory"
        factory.lat = -22.9
        factory.lng = -47.0
        factory.status = "active"

        product = MagicMock()
        product.material_id = "mat_01"
        product.stock = 100.0
        product.stock_max = 500.0
        product.production_rate_current = 10.0

        warehouse = MagicMock()
        warehouse.id = "wh1"
        warehouse.name = "Jundiai Warehouse"
        warehouse.lat = -23.1
        warehouse.lng = -46.8
        warehouse.status = "active"

        wh_stock = MagicMock()
        wh_stock.material_id = "mat_01"
        wh_stock.stock = 200.0
        wh_stock.min_stock = 50.0

        store = MagicMock()
        store.id = "s1"
        store.name = "SP Centro Store"
        store.lat = -23.5
        store.lng = -46.6
        store.status = "active"

        s_stock = MagicMock()
        s_stock.material_id = "mat_01"
        s_stock.stock = 30.0
        s_stock.demand_rate = 5.0
        s_stock.reorder_point = 20.0

        truck = MagicMock()
        truck.id = "t1"
        truck.truck_type = "proprietario"
        truck.status = "idle"
        truck.current_lat = -23.0
        truck.current_lng = -46.5
        truck.cargo = None
        truck.degradation = 0.15

        factories_result = MagicMock()
        factories_result.scalars.return_value.all.return_value = [factory]
        products_result = MagicMock()
        products_result.scalars.return_value.all.return_value = [product]
        warehouses_result = MagicMock()
        warehouses_result.scalars.return_value.all.return_value = [warehouse]
        wh_stocks_result = MagicMock()
        wh_stocks_result.scalars.return_value.all.return_value = [wh_stock]
        stores_result = MagicMock()
        stores_result.scalars.return_value.all.return_value = [store]
        s_stocks_result = MagicMock()
        s_stocks_result.scalars.return_value.all.return_value = [s_stock]
        trucks_result = MagicMock()
        trucks_result.scalars.return_value.all.return_value = [truck]

        mock_session.execute.side_effect = [
            factories_result,
            products_result,
            warehouses_result,
            wh_stocks_result,
            stores_result,
            s_stocks_result,
            trucks_result,
        ]

        result = export_world_snapshot()

        assert "factories" in result
        assert "warehouses" in result
        assert "stores" in result
        assert "trucks" in result
        assert len(result["factories"]) == 1
        assert result["factories"][0]["id"] == "f1"
        assert len(result["trucks"]) == 1
        assert result["trucks"][0]["id"] == "t1"

    @patch("src.workers.tasks.exports.get_sync_session")
    def test_empty_world(self, mock_get_session, mock_session):
        mock_get_session.return_value = mock_session

        empty_result = MagicMock()
        empty_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [
            empty_result,
            empty_result,
            empty_result,
            empty_result,
            empty_result,
            empty_result,
            empty_result,
        ]

        result = export_world_snapshot()

        assert result["factories"] == []
        assert result["warehouses"] == []
        assert result["stores"] == []
        assert result["trucks"] == []
