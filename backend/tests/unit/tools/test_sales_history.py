from src.tools.sales_history import sales_history


class TestSalesHistoryTool:
    def test_is_langchain_tool(self):
        assert hasattr(sales_history, "name")
        assert sales_history.name == "sales_history"

    def test_returns_valid_result(self):
        result = sales_history.invoke({
            "entity_id": "store-001",
            "material_id": "mat-001",
            "last_n_ticks": 30,
        })
        assert hasattr(result, "entity_id")
        assert hasattr(result, "material_id")
        assert hasattr(result, "total_sold")
        assert hasattr(result, "average_per_tick")
        assert hasattr(result, "trend")

    def test_trend_is_valid_value(self):
        result = sales_history.invoke({
            "entity_id": "store-001",
            "material_id": "mat-001",
            "last_n_ticks": 30,
        })
        assert result.trend in ("increasing", "stable", "decreasing")

    def test_values_non_negative(self):
        result = sales_history.invoke({
            "entity_id": "warehouse-001",
            "material_id": "mat-002",
            "last_n_ticks": 10,
        })
        assert result.total_sold >= 0
        assert result.average_per_tick >= 0

    def test_echoes_input_ids(self):
        result = sales_history.invoke({
            "entity_id": "factory-abc",
            "material_id": "mat-xyz",
            "last_n_ticks": 5,
        })
        assert result.entity_id == "factory-abc"
        assert result.material_id == "mat-xyz"

    def test_deterministic_same_inputs(self):
        args = {
            "entity_id": "store-001",
            "material_id": "mat-001",
            "last_n_ticks": 30,
        }
        r1 = sales_history.invoke(args)
        r2 = sales_history.invoke(args)
        assert r1.total_sold == r2.total_sold
        assert r1.trend == r2.trend
