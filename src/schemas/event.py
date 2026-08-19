from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class ProductEventRequest(BaseModel):
    product_id: str
    seller_id: str
    event: str
    date: datetime


class IncomingB2BEvent(BaseModel):
    event_type: Literal["PRODUCT_CREATED", "PRODUCT_EDITED", "PRODUCT_DELETED", "CREATED", "EDITED", "DELETED"]
    idempotency_key: str
    occurred_at: datetime
    payload: dict[str, Any]
