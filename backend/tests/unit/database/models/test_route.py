from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import JSON
from src.database.models import Route


def test_table_name():
    assert Route.__tablename__ == "routes"


def test_id_is_uuid():
    col = Route.__table__.columns["id"]
    assert isinstance(col.type, UUID)


def test_path_is_json_type():
    col = Route.__table__.columns["path"]
    assert isinstance(col.type, (JSONB, JSON))


def test_timestamps_is_json_type():
    col = Route.__table__.columns["timestamps"]
    assert isinstance(col.type, (JSONB, JSON))


def test_completed_at_is_nullable():
    col = Route.__table__.columns["completed_at"]
    assert col.nullable is True
