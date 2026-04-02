from sqlalchemy import inspect
from src.database.models import Factory, FactoryProduct, FactoryPartnerWarehouse


def test_factory_table_name():
    assert Factory.__tablename__ == "factories"


def test_factory_product_table_name():
    assert FactoryProduct.__tablename__ == "factory_products"


def test_factory_partner_warehouses_table_name():
    assert FactoryPartnerWarehouse.__tablename__ == "factory_partner_warehouses"


def test_factory_product_composite_pk():
    pk_columns = {col.name for col in FactoryProduct.__table__.primary_key}
    assert "factory_id" in pk_columns
    assert "material_id" in pk_columns


def test_factory_product_stock_reserved_default():
    product = FactoryProduct()
    assert product.stock_reserved == 0


def test_factory_partner_warehouse_composite_pk():
    pk_columns = {col.name for col in FactoryPartnerWarehouse.__table__.primary_key}
    assert "factory_id" in pk_columns
    assert "warehouse_id" in pk_columns


def test_factory_has_status_column():
    column_names = {col.key for col in inspect(Factory).mapper.column_attrs}
    assert "status" in column_names
