from src.tools.stock_levels import factory_stock_levels, warehouse_stock_levels


class TestWarehouseStockLevelsTool:
    def test_is_langchain_tool(self):
        assert hasattr(warehouse_stock_levels, "name")
        assert warehouse_stock_levels.name == "warehouse_stock_levels"

    def test_returns_valid_result(self):
        result = warehouse_stock_levels.invoke({"warehouse_id": "wh-001"})
        assert hasattr(result, "warehouse_id")
        assert hasattr(result, "stocks")
        assert isinstance(result.stocks, list)

    def test_echoes_warehouse_id(self):
        result = warehouse_stock_levels.invoke({"warehouse_id": "wh-abc"})
        assert result.warehouse_id == "wh-abc"

    def test_stock_items_have_required_fields(self):
        result = warehouse_stock_levels.invoke({"warehouse_id": "wh-001"})
        for item in result.stocks:
            assert hasattr(item, "material_id")
            assert hasattr(item, "quantity")
            assert hasattr(item, "capacity_remaining")


class TestFactoryStockLevelsTool:
    def test_is_langchain_tool(self):
        assert hasattr(factory_stock_levels, "name")
        assert factory_stock_levels.name == "factory_stock_levels"

    def test_returns_valid_result(self):
        result = factory_stock_levels.invoke({"factory_id": "fac-001"})
        assert hasattr(result, "factory_id")
        assert hasattr(result, "products")
        assert isinstance(result.products, list)

    def test_echoes_factory_id(self):
        result = factory_stock_levels.invoke({"factory_id": "fac-xyz"})
        assert result.factory_id == "fac-xyz"

    def test_product_items_have_required_fields(self):
        result = factory_stock_levels.invoke({"factory_id": "fac-001"})
        for item in result.products:
            assert hasattr(item, "material_id")
            assert hasattr(item, "stock")
            assert hasattr(item, "stock_max")
            assert hasattr(item, "production_rate_current")
