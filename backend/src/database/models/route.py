import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from . import Base


class Route(Base):
    __tablename__ = "routes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    truck_id = Column(String(50), ForeignKey("trucks.id"), nullable=False)
    origin_type = Column(String(20), nullable=False)
    origin_id = Column(String(50), nullable=False)
    dest_type = Column(String(20), nullable=False)
    dest_id = Column(String(50), nullable=False)
    path = Column(JSONB, nullable=False)
    timestamps = Column(JSONB, nullable=False)
    eta_ticks = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("pending_orders.id"), nullable=True)
    leg = Column(String(20), nullable=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=False)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
