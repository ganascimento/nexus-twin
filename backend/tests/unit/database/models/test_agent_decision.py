from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID
from src.database.models import AgentDecision


def test_table_name():
    assert AgentDecision.__tablename__ == "agent_decisions"


def test_id_is_uuid():
    col = AgentDecision.__table__.columns["id"]
    assert isinstance(col.type, UUID)


def test_reasoning_is_nullable():
    col = AgentDecision.__table__.columns["reasoning"]
    assert col.nullable is True


def test_required_columns_exist():
    column_names = {col.key for col in inspect(AgentDecision).mapper.column_attrs}
    required = {"agent_type", "entity_id", "tick", "event_type", "action", "payload"}
    assert required.issubset(column_names)
