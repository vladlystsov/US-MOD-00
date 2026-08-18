from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class GetNextRequest(BaseModel):
    """Legacy request name retained for compatibility with imports."""
    queueId: Optional[int] = Field(None, ge=1, le=4)


class ClaimRequest(BaseModel):
    queue_priority: Optional[int] = None
    category_ids: Optional[list[str]] = None


class TicketResponse(BaseModel):
    id: str
    product_id: str
    seller_id: str
    kind: str
    status: str
    queue_priority: int
    category_id: Optional[str] = None
    assigned_moderator_id: Optional[str] = None
    claimed_at: Optional[datetime] = None
    claim_expires_at: Optional[datetime] = None
    decision_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class ApproveRequest(BaseModel):
    comment: Optional[str] = Field(None, max_length=2000)


class FieldReportRequest(BaseModel):
    field_path: str
    message: str = Field(..., max_length=1000)
    severity: Optional[str] = "ERROR"


class BlockDecisionRequest(BaseModel):
    blocking_reason_ids: list[str] = Field(..., min_length=1)
    comment: Optional[str] = Field(None, max_length=2000)
    field_reports: list[FieldReportRequest] = Field(default_factory=list)
