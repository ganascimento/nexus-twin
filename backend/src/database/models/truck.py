from sqlalchemy import Column, String, Float, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from . import Base


class Truck(Base):
    __tablename__ = "trucks"

    id = Column(String(50), primary_key=True)
    truck_type = Column(String(20), nullable=False)
    capacity_tons = Column(Float, nullable=False)
    base_lat = Column(Float, nullable=False)
    base_lng = Column(Float, nullable=False)
    current_lat = Column(Float, nullable=False)
    current_lng = Column(Float, nullable=False)
    degradation = Column(Float, nullable=False)
    breakdown_risk = Column(Float, nullable=False)
    status = Column(String(20), nullable=False)
    factory_id = Column(String(50), ForeignKey("factories.id"), nullable=True)
    cargo = Column(JSONB, nullable=True)
    active_route_id = Column(
        String(50),
        ForeignKey("routes.id", use_alter=True, name="fk_truck_active_route"),
        nullable=True,
    )
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
