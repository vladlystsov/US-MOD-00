from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies.moderator_auth import get_current_moderator_id
from src.schemas.moderation import ApproveRequest, BlockDecisionRequest, TicketResponse
from src.services.ticket_service import TicketService

router = APIRouter(prefix="/api/v1/tickets", tags=["Tickets"])


@router.post("/{ticket_id}/approve", response_model=TicketResponse)
def approve_ticket(
    ticket_id: str,
    payload: Optional[ApproveRequest] = None,
    db: Session = Depends(get_db),
    moderator_id: str = Depends(get_current_moderator_id),
):
    result = TicketService(db).approve(ticket_id, moderator_id, payload.comment if payload else None)
    if result.get("code") == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=result)
    if result.get("code") == "FORBIDDEN":
        raise HTTPException(status_code=403, detail=result)
    if result.get("code") in {"TICKET_WRONG_STATUS", "TICKET_NOT_ASSIGNED", "NO_SKUS"}:
        raise HTTPException(status_code=409, detail=result)
    return result["ticket"]


@router.post("/{ticket_id}/block", response_model=TicketResponse)
def block_ticket(
    ticket_id: str,
    payload: BlockDecisionRequest,
    db: Session = Depends(get_db),
    moderator_id: str = Depends(get_current_moderator_id),
):
    result = TicketService(db).block(
        ticket_id=ticket_id,
        moderator_id=moderator_id,
        reason_ids=payload.blocking_reason_ids,
        comment=payload.comment,
        field_reports=[report.model_dump() for report in payload.field_reports],
    )
    if result.get("code") == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=result)
    if result.get("code") == "FORBIDDEN":
        raise HTTPException(status_code=403, detail=result)
    if result.get("code") in {"TICKET_WRONG_STATUS", "TICKET_NOT_ASSIGNED"}:
        raise HTTPException(status_code=409, detail=result)
    if result.get("code") == "INVALID_BLOCKING_REASON":
        raise HTTPException(status_code=400, detail=result)
    return result["ticket"]
