import uuid
from sqlalchemy import Column, String, Float, Integer, Text, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from . import Base


class PendingOrder(Base):
    __tablename__ = "pending_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requester_type = Column(String(20), nullable=False)
    requester_id = Column(String(50), nullable=False)
    target_type = Column(String(20), nullable=False)
    target_id = Column(String(50), nullable=False)
    material_id = Column(String(50), ForeignKey("materials.id"), nullable=False)
    quantity_tons = Column(Float, nullable=False)
    status = Column(String(20), nullable=False)
    age_ticks = Column(Integer, nullable=False, default=0)
    retry_after_tick = Column(Integer, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    eta_ticks = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
