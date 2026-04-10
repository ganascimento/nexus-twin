from unittest.mock import MagicMock, patch

import pytest
from src.workers.tasks.reports import (
    generate_decision_summary,
    generate_efficiency_report,
)


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


class TestGenerateEfficiencyReport:
    @patch("src.workers.tasks.reports.get_sync_session")
    def test_returns_all_required_keys(self, mock_get_session, mock_session):
        mock_get_session.return_value = mock_session

        delivered_result = MagicMock()
        delivered_result.scalar.return_value = 5

        late_result = MagicMock()
        late_result.scalar.return_value = 2

        store_rupture = MagicMock()
        store_rupture.store_id = "store_01"
        store_rupture.material_id = "mat_01"

        warehouse_rupture = MagicMock()
        warehouse_rupture.warehouse_id = "wh_01"
        warehouse_rupture.material_id = "mat_02"

        store_ruptures_result = MagicMock()
        store_ruptures_result.all.return_value = [store_rupture]

        warehouse_ruptures_result = MagicMock()
        warehouse_ruptures_result.all.return_value = [warehouse_rupture]

        truck = MagicMock()
        truck.id = "truck_01"
        truck.status = "in_transit"
        truck2 = MagicMock()
        truck2.id = "truck_02"
        truck2.status = "idle"

        trucks_result = MagicMock()
        trucks_result.scalars.return_value.all.return_value = [truck, truck2]

        mock_session.execute.side_effect = [
            delivered_result,
            late_result,
            store_ruptures_result,
            warehouse_ruptures_result,
            trucks_result,
        ]

        result = generate_efficiency_report()

        assert result["orders_delivered"] == 5
        assert result["orders_late"] == 2
        assert len(result["stock_ruptures"]) == 2
        assert result["stock_ruptures"][0]["entity_type"] == "store"
        assert result["stock_ruptures"][0]["entity_id"] == "store_01"
        assert result["stock_ruptures"][1]["entity_type"] == "warehouse"
        assert result["stock_ruptures"][1]["entity_id"] == "wh_01"
        assert "truck_01" in result["truck_utilization"]
        assert "truck_02" in result["truck_utilization"]

    @patch("src.workers.tasks.reports.get_sync_session")
    def test_empty_data_returns_zero_counts(self, mock_get_session, mock_session):
        mock_get_session.return_value = mock_session

        delivered_result = MagicMock()
        delivered_result.scalar.return_value = 0
        late_result = MagicMock()
        late_result.scalar.return_value = 0
        store_ruptures_result = MagicMock()
        store_ruptures_result.all.return_value = []
        warehouse_ruptures_result = MagicMock()
        warehouse_ruptures_result.all.return_value = []
        trucks_result = MagicMock()
        trucks_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [
            delivered_result,
            late_result,
            store_ruptures_result,
            warehouse_ruptures_result,
            trucks_result,
        ]

        result = generate_efficiency_report()

        assert result["orders_delivered"] == 0
        assert result["orders_late"] == 0
        assert result["stock_ruptures"] == []
        assert result["truck_utilization"] == {}

    @patch("src.workers.tasks.reports.get_sync_session")
    def test_truck_utilization_has_status_field(self, mock_get_session, mock_session):
        mock_get_session.return_value = mock_session

        delivered_result = MagicMock()
        delivered_result.scalar.return_value = 0
        late_result = MagicMock()
        late_result.scalar.return_value = 0
        store_ruptures_result = MagicMock()
        store_ruptures_result.all.return_value = []
        warehouse_ruptures_result = MagicMock()
        warehouse_ruptures_result.all.return_value = []

        truck = MagicMock()
        truck.id = "truck_01"
        truck.status = "in_transit"
        trucks_result = MagicMock()
        trucks_result.scalars.return_value.all.return_value = [truck]

        mock_session.execute.side_effect = [
            delivered_result,
            late_result,
            store_ruptures_result,
            warehouse_ruptures_result,
            trucks_result,
        ]

        result = generate_efficiency_report()

        assert result["truck_utilization"]["truck_01"]["status"] == "in_transit"


class TestGenerateDecisionSummary:
    @patch("src.workers.tasks.reports.get_sync_session")
    def test_groups_by_agent_type_and_action(self, mock_get_session, mock_session):
        mock_get_session.return_value = mock_session

        row1 = MagicMock()
        row1.agent_type = "factory"
        row1.action = "start_production"
        row1.count = 3
        row2 = MagicMock()
        row2.agent_type = "warehouse"
        row2.action = "request_resupply"
        row2.count = 2
        row3 = MagicMock()
        row3.agent_type = "factory"
        row3.action = "send_stock"
        row3.count = 1

        query_result = MagicMock()
        query_result.all.return_value = [row1, row2, row3]
        mock_session.execute.return_value = query_result

        result = generate_decision_summary(tick_start=1, tick_end=24)

        assert result["factory"]["start_production"] == 3
        assert result["factory"]["send_stock"] == 1
        assert result["warehouse"]["request_resupply"] == 2

    @patch("src.workers.tasks.reports.get_sync_session")
    def test_default_tick_range_uses_last_24(self, mock_get_session, mock_session):
        mock_get_session.return_value = mock_session

        max_tick_result = MagicMock()
        max_tick_result.scalar.return_value = 50

        query_result = MagicMock()
        query_result.all.return_value = []

        mock_session.execute.side_effect = [max_tick_result, query_result]

        result = generate_decision_summary()

        assert result == {}
        assert mock_session.execute.call_count == 2

    @patch("src.workers.tasks.reports.get_sync_session")
    def test_no_decisions_returns_empty_dict(self, mock_get_session, mock_session):
        mock_get_session.return_value = mock_session

        query_result = MagicMock()
        query_result.all.return_value = []
        mock_session.execute.return_value = query_result

        result = generate_decision_summary(tick_start=1, tick_end=24)

        assert result == {}
