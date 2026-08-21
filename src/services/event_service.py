from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.models.processed_b2b_event import ProcessedB2BEvent
from src.models.product_moderation import ProductModeration
from src.models.field_report import ProductModerationFieldReport
import httpx
import uuid
from datetime import datetime, timedelta
from src.config import settings


INBOUND_IDEMPOTENCY_TTL = timedelta(hours=24)


class EventService:
    def __init__(self, db: Session):
        self.db = db

    def handle_product_event(self, payload: dict) -> dict:
        product_id = payload.get("product_id")
        seller_id = payload.get("seller_id")
        event_type = payload.get("event")
        idempotency_key = payload.get("idempotency_key")

        # The insert is flushed before touching the ticket. A unique key is the
        # concurrency guard for replayed deliveries of the same B2B envelope.
        # The receipt is kept for exactly the contractually required 24 hours.
        if idempotency_key:
            now = datetime.utcnow()
            self.db.query(ProcessedB2BEvent).filter(
                ProcessedB2BEvent.created_at <= now - INBOUND_IDEMPOTENCY_TTL
            ).delete(synchronize_session=False)
            try:
                self.db.add(
                    ProcessedB2BEvent(
                        idempotency_key=idempotency_key,
                        event_type=event_type or "UNKNOWN",
                        product_id=product_id,
                    )
                )
                self.db.flush()
            except IntegrityError:
                self.db.rollback()
                return {"status": "duplicate"}

        existing = self.db.query(ProductModeration).filter(
            ProductModeration.product_id == product_id
        ).first()

        if event_type == "CREATED":
            result = self._handle_created(product_id, seller_id, existing)
        elif event_type == "EDITED":
            result = self._handle_edited(product_id, existing)
        elif event_type == "DELETED":
            result = self._handle_deleted(product_id, existing)
        else:
            result = {"status": "unknown_event"}

        if result.get("status") == "b2b_error":
            self.db.rollback()
            return result
        # Handlers that changed a ticket already commit. A second commit is safe
        # and persists a receipt for no-op events such as repeated deletes.
        self.db.commit()
        return result

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
        elif old_status in {"MODERATED", "APPROVED"}:
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
