from sqlalchemy import Column, String, Float, ForeignKey, TIMESTAMP, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from . import Base


class Store(Base):
    __tablename__ = "stores"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    status = Column(String(20), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    stocks = relationship("StoreStock", lazy="selectin")


class StoreStock(Base):
    __tablename__ = "store_stocks"
    __table_args__ = (PrimaryKeyConstraint("store_id", "material_id"),)

    store_id = Column(String(50), ForeignKey("stores.id"), nullable=False)
    material_id = Column(String(50), ForeignKey("materials.id"), nullable=False)
    stock = Column(Float, nullable=False)
    demand_rate = Column(Float, nullable=False)
    reorder_point = Column(Float, nullable=False)
