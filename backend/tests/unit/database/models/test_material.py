from sqlalchemy import inspect
from src.database.models import Material


def test_table_name():
    assert Material.__tablename__ == "materials"


def test_columns_exist():
    column_names = {col.key for col in inspect(Material).mapper.column_attrs}
    assert {"id", "name", "is_active", "created_at"}.issubset(column_names)


def test_id_is_primary_key():
    pk_columns = {col.name for col in Material.__table__.primary_key}
    assert "id" in pk_columns


def test_is_active_default():
    material = Material(id="x", name="X")
    assert material.is_active is True
