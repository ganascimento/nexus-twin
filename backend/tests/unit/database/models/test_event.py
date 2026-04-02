from sqlalchemy.dialects.postgresql import UUID
from src.database.models import ChaosEvent


def test_table_name():
    assert ChaosEvent.__tablename__ == "events"


def test_id_is_uuid():
    col = ChaosEvent.__table__.columns["id"]
    assert isinstance(col.type, UUID)


def test_entity_fields_are_nullable():
    assert ChaosEvent.__table__.columns["entity_type"].nullable is True
    assert ChaosEvent.__table__.columns["entity_id"].nullable is True


def test_tick_end_is_nullable():
    col = ChaosEvent.__table__.columns["tick_end"]
    assert col.nullable is True
