import uuid

from sqlalchemy import Boolean, Column, String, Text

from src.database import Base


class BlockingReason(Base):
    __tablename__ = "blocking_reasons"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(64), nullable=False, unique=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    hard_block = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
