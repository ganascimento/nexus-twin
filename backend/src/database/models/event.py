import uuid
from sqlalchemy import Column, String, Integer, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from . import Base


class ChaosEvent(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False)
    source = Column(String(50), nullable=False)
    entity_type = Column(String(20), nullable=True)
    entity_id = Column(String(50), nullable=True)
    payload = Column(JSONB, nullable=False)
    status = Column(String(20), nullable=False)
    tick_start = Column(Integer, nullable=False)
    tick_end = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
