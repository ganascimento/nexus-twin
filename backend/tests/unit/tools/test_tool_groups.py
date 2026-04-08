from src.tools import (
    FACTORY_TOOLS,
    STORE_TOOLS,
    TRUCK_TOOLS,
    WAREHOUSE_TOOLS,
    factory_stock_levels,
    route_risk,
    sales_history,
    warehouse_stock_levels,
    weather,
)


class TestToolGroups:
    def test_factory_tools(self):
        assert FACTORY_TOOLS == [sales_history, warehouse_stock_levels]

    def test_warehouse_tools(self):
        assert WAREHOUSE_TOOLS == [sales_history, factory_stock_levels]

    def test_store_tools(self):
        assert STORE_TOOLS == [sales_history, warehouse_stock_levels]

    def test_truck_tools(self):
        assert TRUCK_TOOLS == [weather, route_risk]
