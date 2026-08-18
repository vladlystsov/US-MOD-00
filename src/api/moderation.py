from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies.moderator_auth import get_current_moderator_id
from src.schemas.moderation import ClaimRequest, TicketResponse
from src.services.ticket_service import TicketService

router = APIRouter(prefix="/api/v1/queue", tags=["Queue"])


@router.post("/claim", response_model=TicketResponse)
def claim_next_card(
    payload: Optional[ClaimRequest] = None,
    db: Session = Depends(get_db),
    moderator_id: str = Depends(get_current_moderator_id),
):
    result = TicketService(db).claim_next(
        moderator_id=moderator_id,
        queue_priority=payload.queue_priority if payload else None,
        category_ids=payload.category_ids if payload else None,
    )
    if result.get("status") == "empty":
        return Response(status_code=204)
    if result.get("code") == "INVALID_QUEUE":
        raise HTTPException(status_code=400, detail=result)
    if result.get("code") == "MODERATOR_BUSY":
        raise HTTPException(status_code=409, detail=result)
    return result["ticket"]
