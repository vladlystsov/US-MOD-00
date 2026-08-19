from fastapi import APIRouter, Depends, Response
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
    EventService(db).handle_product_event(
        {
            "product_id": payload.get("product_id"),
            "seller_id": payload.get("seller_id", ""),
            "event": event_map[event.event_type],
            "date": event.occurred_at,
        }
    )
    return Response(status_code=202)
