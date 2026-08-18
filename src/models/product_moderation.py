from sqlalchemy import Column, String, DateTime, JSON, Integer, Text
from sqlalchemy.sql import func
from src.database import Base


class ProductModeration(Base):
    __tablename__ = "product_moderation"

    id = Column(String(36), primary_key=True)
    product_id = Column(String(36), unique=True, nullable=False, index=True)
    seller_id = Column(String(36), nullable=False)
    status = Column(String(50), nullable=False, default="PENDING")
    queue_priority = Column(Integer, nullable=False, default=1)
    json_before = Column(JSON, nullable=True)
    json_after = Column(JSON, nullable=False)
    blocking_reason_id = Column(String(36), nullable=True)
    moderator_id = Column(String(36), nullable=True)
    moderator_comment = Column(Text, nullable=True)
    total_active_quantity = Column(Integer, nullable=True)
    date_created = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    date_updated = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    date_moderation = Column(DateTime(timezone=True), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    claim_expires_at = Column(DateTime(timezone=True), nullable=True)
