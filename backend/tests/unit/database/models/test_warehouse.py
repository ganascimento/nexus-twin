from sqlalchemy import inspect
from src.database.models import Warehouse, WarehouseStock


def test_warehouse_table_name():
    assert Warehouse.__tablename__ == "warehouses"


def test_warehouse_stock_table_name():
    assert WarehouseStock.__tablename__ == "warehouse_stocks"


def test_warehouse_stock_composite_pk():
    pk_columns = {col.name for col in WarehouseStock.__table__.primary_key}
    assert "warehouse_id" in pk_columns
    assert "material_id" in pk_columns


def test_warehouse_stock_stock_reserved_default():
    stock = WarehouseStock()
    assert stock.stock_reserved == 0


def test_warehouse_has_region_column():
    column_names = {col.key for col in inspect(Warehouse).mapper.column_attrs}
    assert "region" in column_names
