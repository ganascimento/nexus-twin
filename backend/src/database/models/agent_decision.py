import uuid
from sqlalchemy import Column, String, Integer, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from . import Base


class AgentDecision(Base):
    __tablename__ = "agent_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_type = Column(String(20), nullable=False)
    entity_id = Column(String(50), nullable=False)
    tick = Column(Integer, nullable=False)
    event_type = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)
    payload = Column(JSONB, nullable=False)
    reasoning = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
