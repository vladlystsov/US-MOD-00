from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies.moderator_auth import get_current_admin_id, get_current_moderator_id
from src.models.blocking_reason import BlockingReason
from src.models.product_moderation import ProductModeration
from src.schemas.blocking_reason import (
    BlockingReasonCreateRequest,
    BlockingReasonResponse,
    BlockingReasonUpdateRequest,
)

router = APIRouter(prefix="/api/v1/blocking-reasons", tags=["Blocking Reasons"])


@router.get("", response_model=list[BlockingReasonResponse])
def list_blocking_reasons(
    hard_block: Optional[bool] = None,
    is_active: bool = True,
    _: str = Depends(get_current_moderator_id),
    db: Session = Depends(get_db),
):
    query = db.query(BlockingReason).filter(BlockingReason.is_active.is_(is_active))
    if hard_block is not None:
        query = query.filter(BlockingReason.hard_block.is_(hard_block))
    return query.order_by(BlockingReason.code.asc()).all()


@router.post("", response_model=BlockingReasonResponse, status_code=201)
def create_blocking_reason(
    payload: BlockingReasonCreateRequest,
    _: str = Depends(get_current_admin_id),
    db: Session = Depends(get_db),
):
    existing = db.query(BlockingReason).filter(BlockingReason.code == payload.code).first()
    if existing:
        raise HTTPException(status_code=409, detail={"code": "DUPLICATE_CODE", "message": "Blocking reason code already exists"})
    reason = BlockingReason(**payload.model_dump())
    db.add(reason)
    db.commit()
    db.refresh(reason)
    return reason


@router.patch("/{reason_id}", response_model=BlockingReasonResponse)
def update_blocking_reason(
    reason_id: str,
    payload: BlockingReasonUpdateRequest,
    _: str = Depends(get_current_admin_id),
    db: Session = Depends(get_db),
):
    reason = db.query(BlockingReason).filter(BlockingReason.id == reason_id).first()
    if not reason:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Blocking reason not found"})
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(reason, key, value)
    db.commit()
    db.refresh(reason)
    return reason


@router.delete("/{reason_id}", status_code=204)
def deactivate_blocking_reason(
    reason_id: str,
    _: str = Depends(get_current_admin_id),
    db: Session = Depends(get_db),
):
    reason = db.query(BlockingReason).filter(BlockingReason.id == reason_id).first()
    if not reason:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Blocking reason not found"})
    is_referenced = db.query(ProductModeration).filter(ProductModeration.blocking_reason_id == reason_id).first()
    if is_referenced:
        raise HTTPException(status_code=409, detail={"code": "REFERENCED_REASON", "message": "Blocking reason is referenced by a ticket"})
    reason.is_active = False
    db.commit()
    return Response(status_code=204)
