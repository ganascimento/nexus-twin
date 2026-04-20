from src.tools import (
    FACTORY_TOOLS,
    STORE_TOOLS,
    TRUCK_TOOLS,
    WAREHOUSE_TOOLS,
)


class TestToolGroups:
    def test_factory_tools_empty_by_default(self):
        assert FACTORY_TOOLS == []

    def test_warehouse_tools_empty_by_default(self):
        assert WAREHOUSE_TOOLS == []

    def test_store_tools_empty_by_default(self):
        assert STORE_TOOLS == []

    def test_truck_tools_empty_by_default(self):
        assert TRUCK_TOOLS == []
