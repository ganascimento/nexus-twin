from sqlalchemy import Column, String, Boolean, TIMESTAMP
from sqlalchemy.sql import func

from . import Base


class Material(Base):
    __tablename__ = "materials"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
