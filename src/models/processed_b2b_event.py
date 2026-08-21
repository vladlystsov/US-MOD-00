from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func

from src.database import Base


class ProcessedB2BEvent(Base):
    """One accepted incoming B2B event, retained for idempotency handling."""

    __tablename__ = "processed_b2b_events"

    idempotency_key = Column(String(64), primary_key=True)
    event_type = Column(String(64), nullable=False)
    product_id = Column(String(36), nullable=True, index=True)
    # Receipts expire 24 hours after created_at; retaining the existing column
    # avoids a schema migration for deployed SQLite databases.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
