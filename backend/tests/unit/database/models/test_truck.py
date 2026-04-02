from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON
from src.database.models import Truck


def test_table_name():
    assert Truck.__tablename__ == "trucks"


def test_has_position_columns():
    column_names = {col.key for col in inspect(Truck).mapper.column_attrs}
    assert {"base_lat", "base_lng", "current_lat", "current_lng"}.issubset(column_names)


def test_factory_id_is_nullable():
    col = Truck.__table__.columns["factory_id"]
    assert col.nullable is True


def test_active_route_id_is_nullable():
    col = Truck.__table__.columns["active_route_id"]
    assert col.nullable is True


def test_cargo_is_json_type():
    col = Truck.__table__.columns["cargo"]
    assert isinstance(col.type, (JSONB, JSON))
