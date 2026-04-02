from sqlalchemy import Column, String, Float, Integer, ForeignKey, TIMESTAMP, PrimaryKeyConstraint
from sqlalchemy.sql import func

from . import Base


class Factory(Base):
    __tablename__ = "factories"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    status = Column(String(20), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class FactoryProduct(Base):
    __tablename__ = "factory_products"
    __table_args__ = (PrimaryKeyConstraint("factory_id", "material_id"),)

    factory_id = Column(String(50), ForeignKey("factories.id"), nullable=False)
    material_id = Column(String(50), ForeignKey("materials.id"), nullable=False)
    stock = Column(Float, nullable=False)
    stock_reserved = Column(Float, nullable=False, default=0)
    stock_max = Column(Float, nullable=False)
    production_rate_max = Column(Float, nullable=False)
    production_rate_current = Column(Float, nullable=False)


class FactoryPartnerWarehouse(Base):
    __tablename__ = "factory_partner_warehouses"
    __table_args__ = (PrimaryKeyConstraint("factory_id", "warehouse_id"),)

    factory_id = Column(String(50), ForeignKey("factories.id"), nullable=False)
    warehouse_id = Column(String(50), ForeignKey("warehouses.id"), nullable=False)
    priority = Column(Integer, nullable=False)
