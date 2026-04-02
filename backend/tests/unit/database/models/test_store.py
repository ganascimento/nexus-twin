from sqlalchemy import inspect
from src.database.models import Store, StoreStock


def test_store_table_name():
    assert Store.__tablename__ == "stores"


def test_store_stock_table_name():
    assert StoreStock.__tablename__ == "store_stocks"


def test_store_stock_composite_pk():
    pk_columns = {col.name for col in StoreStock.__table__.primary_key}
    assert "store_id" in pk_columns
    assert "material_id" in pk_columns


def test_store_stock_has_demand_rate_column():
    column_names = {col.key for col in inspect(StoreStock).mapper.column_attrs}
    assert "demand_rate" in column_names


def test_store_stock_has_reorder_point_column():
    column_names = {col.key for col in inspect(StoreStock).mapper.column_attrs}
    assert "reorder_point" in column_names
