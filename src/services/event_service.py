from sqlalchemy.orm import Session
from src.models.product_moderation import ProductModeration
from src.models.field_report import ProductModerationFieldReport
import httpx
import uuid
from datetime import datetime
from src.config import settings


class EventService:
    def __init__(self, db: Session):
        self.db = db

    def handle_product_event(self, payload: dict) -> dict:
        product_id = payload.get("product_id")
        seller_id = payload.get("seller_id")
        event_type = payload.get("event")

        existing = self.db.query(ProductModeration).filter(
            ProductModeration.product_id == product_id
        ).first()

        if event_type == "CREATED":
            return self._handle_created(product_id, seller_id, existing)
        elif event_type == "EDITED":
            return self._handle_edited(product_id, existing)
        elif event_type == "DELETED":
            return self._handle_deleted(product_id, existing)

        return {"status": "unknown_event"}

    def _handle_created(self, product_id: str, seller_id: str, existing) -> dict:
        if existing:
            if existing.status == "HARD_BLOCKED":
                return {"status": "accepted"}
            return {"status": "duplicate"}

        product_data = self._fetch_product_from_b2b(product_id)
        if not product_data:
            return {"status": "b2b_error"}

        total_active = sum(
            sku.get("active_quantity", 0)
            for sku in product_data.get("skus", [])
        )

        moderation = ProductModeration(
            id=str(uuid.uuid4()),
            product_id=product_id,
            seller_id=seller_id,
            status="PENDING",
            queue_priority=1,
            json_before=None,
            json_after=product_data,
            total_active_quantity=total_active
        )
        self.db.add(moderation)
        self.db.commit()

        return {"status": "accepted"}

    def _handle_edited(self, product_id: str, existing) -> dict:
        if not existing:
            return {"status": "not_found"}

        if existing.status == "HARD_BLOCKED":
            return {"status": "accepted"}

        product_data = self._fetch_product_from_b2b(product_id)
        if not product_data:
            return {"status": "b2b_error"}

        old_status = existing.status

        total_active = sum(
            sku.get("active_quantity", 0)
            for sku in product_data.get("skus", [])
        )

        if old_status == "BLOCKED":
            queue_priority = 2
        elif old_status == "MODERATED":
            queue_priority = 3 if total_active > 0 else 4
        else:
            queue_priority = existing.queue_priority

        existing.json_before = existing.json_after
        existing.json_after = product_data
        existing.status = "PENDING"
        existing.queue_priority = queue_priority
        existing.moderator_id = None
        existing.claimed_at = None
        existing.claim_expires_at = None
        existing.total_active_quantity = total_active
        existing.date_updated = datetime.utcnow()

        self.db.query(ProductModerationFieldReport).filter(
            ProductModerationFieldReport.product_moderation_id == existing.id
        ).delete()

        self.db.commit()

        return {"status": "accepted"}

    def _handle_deleted(self, product_id: str, existing) -> dict:
        if not existing:
            return {"status": "accepted"}

        self.db.delete(existing)
        self.db.commit()

        return {"status": "accepted"}

    def _fetch_product_from_b2b(self, product_id: str) -> dict | None:
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{settings.B2B_SERVICE_URL}/api/v1/products/{product_id}",
                    headers={"X-Service-Key": settings.MOD_TO_B2B_KEY},
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return None
