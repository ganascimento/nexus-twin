from sqlalchemy import Column, String, Float, ForeignKey, TIMESTAMP, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from . import Base


class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    region = Column(String(100), nullable=False)
    capacity_total = Column(Float, nullable=False)
    status = Column(String(20), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    stocks = relationship("WarehouseStock", lazy="selectin")


class WarehouseStock(Base):
    __tablename__ = "warehouse_stocks"
    __table_args__ = (PrimaryKeyConstraint("warehouse_id", "material_id"),)

    warehouse_id = Column(String(50), ForeignKey("warehouses.id"), nullable=False)
    material_id = Column(String(50), ForeignKey("materials.id"), nullable=False)
    stock = Column(Float, nullable=False)
    stock_reserved = Column(Float, nullable=False, default=0)
    min_stock = Column(Float, nullable=False)
