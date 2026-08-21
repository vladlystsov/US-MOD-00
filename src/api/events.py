from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies.service_key import verify_service_key
from src.schemas.event import IncomingB2BEvent, ProductEventRequest
from src.services.event_service import EventService

router = APIRouter(prefix="/api/v1/events", tags=["Events"])
b2b_router = APIRouter(prefix="/api/v1/b2b", tags=["B2B Events"])


@router.post("/product")
def handle_product_event(
    payload: ProductEventRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_service_key),
):
    EventService(db).handle_product_event(payload.model_dump())
    return {"accepted": True}


@b2b_router.post("/events", status_code=202)
def handle_b2b_product_event(
    event: IncomingB2BEvent,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_service_key),
):
    event_map = {
        "PRODUCT_CREATED": "CREATED",
        "PRODUCT_EDITED": "EDITED",
        "PRODUCT_DELETED": "DELETED",
        "CREATED": "CREATED",
        "EDITED": "EDITED",
        "DELETED": "DELETED",
    }
    payload = event.payload
    result = EventService(db).handle_product_event(
        {
            "product_id": payload.get("product_id"),
            "seller_id": payload.get("seller_id", ""),
            "event": event_map[event.event_type],
            "date": event.occurred_at,
            "idempotency_key": event.idempotency_key,
        }
    )
    if result.get("status") == "duplicate":
        raise HTTPException(
            status_code=409,
            detail={"code": "DUPLICATE_EVENT", "message": "B2B event has already been processed"},
        )
    if result.get("status") == "b2b_error":
        # EventService has rolled back both ticket work and the idempotency receipt.
        # A non-2xx response keeps the envelope eligible for B2B retry.
        raise HTTPException(
            status_code=503,
            detail={"code": "B2B_UNAVAILABLE", "message": "Could not load current product from B2B; retry delivery"},
        )
    return Response(status_code=202)
