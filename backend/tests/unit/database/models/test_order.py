from sqlalchemy.dialects.postgresql import UUID
from src.database.models import PendingOrder


def test_table_name():
    assert PendingOrder.__tablename__ == "pending_orders"


def test_id_is_uuid():
    col = PendingOrder.__table__.columns["id"]
    assert isinstance(col.type, UUID)


def test_age_ticks_default():
    order = PendingOrder()
    assert order.age_ticks == 0


def test_nullable_fields():
    nullable_columns = ["retry_after_tick", "rejection_reason", "cancellation_reason", "eta_ticks"]
    for col_name in nullable_columns:
        col = PendingOrder.__table__.columns[col_name]
        assert col.nullable is True, f"Expected {col_name} to be nullable"
