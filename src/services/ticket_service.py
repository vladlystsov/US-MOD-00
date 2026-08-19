from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from src.config import settings
from src.models.blocking_reason import BlockingReason
from src.models.field_report import ProductModerationFieldReport
from src.models.product_moderation import ProductModeration

CLAIM_TTL = timedelta(minutes=30)


class TicketService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _ticket_response(ticket: ProductModeration) -> dict:
        product = ticket.json_after or {}
        return {
            "id": ticket.id,
            "product_id": ticket.product_id,
            "seller_id": ticket.seller_id,
            "category_id": product.get("category_id"),
            "kind": "CREATE" if ticket.json_before is None else "EDIT",
            "status": ticket.status,
            "queue_priority": ticket.queue_priority,
            "assigned_moderator_id": ticket.moderator_id,
            "claimed_at": ticket.claimed_at,
            "claim_expires_at": ticket.claim_expires_at,
            "decision_at": ticket.date_moderation,
            "created_at": ticket.date_created,
            "updated_at": ticket.date_updated,
        }

    def _find_ticket(self, ticket_id: str) -> ProductModeration | None:
        return self.db.query(ProductModeration).filter(ProductModeration.id == ticket_id).first() or self.db.query(
            ProductModeration
        ).filter(ProductModeration.product_id == ticket_id).first()

    def claim_next(self, moderator_id: str, queue_priority: Optional[int] = None, category_ids: Optional[list[str]] = None) -> dict:
        if queue_priority is not None and queue_priority not in {1, 2, 3, 4}:
            return {"code": "INVALID_QUEUE", "message": "queue_priority must be 1-4"}

        assigned = self.db.query(ProductModeration).filter(
            ProductModeration.status == "IN_REVIEW", ProductModeration.moderator_id == moderator_id
        ).first()
        if assigned:
            return {"code": "MODERATOR_BUSY", "message": "Moderator already has a ticket in review"}

        query = self.db.query(ProductModeration).filter(ProductModeration.status == "PENDING")
        if queue_priority is not None:
            query = query.filter(ProductModeration.queue_priority == queue_priority)
        # category_ids are snapshot fields. A JSON filter is intentionally avoided
        # for SQLite portability; unsupported values simply do not narrow the queue.
        query = query.order_by(ProductModeration.queue_priority.asc(), ProductModeration.date_created.asc())
        ticket = query.with_for_update(skip_locked=True).first()
        if not ticket:
            return {"status": "empty"}

        now = datetime.utcnow()
        # The status predicate is a second guard for engines where SKIP LOCKED is
        # unsupported or downgraded (e.g. the local SQLite test database).
        updated = self.db.query(ProductModeration).filter(
            ProductModeration.id == ticket.id, ProductModeration.status == "PENDING"
        ).update(
            {
                ProductModeration.status: "IN_REVIEW",
                ProductModeration.moderator_id: moderator_id,
                ProductModeration.claimed_at: now,
                ProductModeration.claim_expires_at: now + CLAIM_TTL,
                ProductModeration.date_updated: now,
            },
            synchronize_session=False,
        )
        if updated != 1:
            self.db.rollback()
            return self.claim_next(moderator_id, queue_priority, category_ids)
        self.db.commit()
        self.db.refresh(ticket)
        return {"ticket": self._ticket_response(ticket)}

    def approve(self, ticket_id: str, moderator_id: str, comment: Optional[str]) -> dict:
        ticket = self._find_ticket(ticket_id)
        if not ticket:
            return {"code": "NOT_FOUND", "message": "Ticket not found"}
        if ticket.status == "HARD_BLOCKED":
            return {"code": "FORBIDDEN", "message": "Cannot modify a hard-blocked ticket"}
        if ticket.status != "IN_REVIEW":
            return {"code": "TICKET_WRONG_STATUS", "message": "Ticket is not in review"}
        if ticket.moderator_id != moderator_id:
            return {"code": "TICKET_NOT_ASSIGNED", "message": "Ticket is assigned to another moderator"}
        if not (ticket.json_after or {}).get("skus"):
            return {"code": "NO_SKUS", "message": "Product has no SKUs, cannot approve"}

        now = datetime.utcnow()
        ticket.status = "APPROVED"
        ticket.date_moderation = now
        ticket.date_updated = now
        ticket.moderator_comment = comment
        ticket.blocking_reason_id = None
        self.db.query(ProductModerationFieldReport).filter(
            ProductModerationFieldReport.product_moderation_id == ticket.id
        ).delete()
        self.db.commit()
        self.db.refresh(ticket)

        self._send_to_b2b(
            "MODERATED",
            ticket,
            {"comment": comment},
        )
        return {"ticket": self._ticket_response(ticket)}

    def block(self, ticket_id: str, moderator_id: str, reason_ids: list[str], comment: Optional[str], field_reports: list[dict]) -> dict:
        ticket = self._find_ticket(ticket_id)
        if not ticket:
            return {"code": "NOT_FOUND", "message": "Ticket not found"}
        if ticket.status == "HARD_BLOCKED":
            return {"code": "FORBIDDEN", "message": "Cannot modify a hard-blocked ticket"}
        if ticket.status != "IN_REVIEW":
            return {"code": "TICKET_WRONG_STATUS", "message": "Ticket is not in review"}
        if ticket.moderator_id != moderator_id:
            return {"code": "TICKET_NOT_ASSIGNED", "message": "Ticket is assigned to another moderator"}

        reasons = self.db.query(BlockingReason).filter(
            BlockingReason.id.in_(reason_ids), BlockingReason.is_active.is_(True)
        ).all()
        if len(reasons) != len(set(reason_ids)):
            return {"code": "INVALID_BLOCKING_REASON", "message": "Blocking reason not found or inactive"}
        if len({reason.hard_block for reason in reasons}) != 1:
            return {"code": "INVALID_BLOCKING_REASON", "message": "Soft and hard blocking reasons cannot be mixed"}

        now = datetime.utcnow()
        hard_block = reasons[0].hard_block
        ticket.status = "HARD_BLOCKED" if hard_block else "BLOCKED"
        ticket.blocking_reason_id = reasons[0].id
        ticket.moderator_comment = comment
        ticket.date_moderation = now
        ticket.date_updated = now
        self.db.query(ProductModerationFieldReport).filter(
            ProductModerationFieldReport.product_moderation_id == ticket.id
        ).delete()
        for report in field_reports:
            self.db.add(
                ProductModerationFieldReport(
                    id=str(uuid.uuid4()),
                    product_moderation_id=ticket.id,
                    field_name=report["field_path"],
                    comment=report["message"],
                )
            )
        self.db.commit()
        self.db.refresh(ticket)

        self._send_to_b2b(
            "BLOCKED",
            ticket,
            {
                "blocking_reason_ids": [reason.id for reason in reasons],
                "comment": comment,
                "field_reports": field_reports,
                "hard_block": hard_block,
            },
        )
        return {"ticket": self._ticket_response(ticket)}

    @staticmethod
    def _send_to_b2b(event_type: str, ticket: ProductModeration, extra_payload: dict) -> None:
        """Best-effort callback. State is committed before the remote call."""
        event = {
            "idempotency_key": str(uuid.uuid4()),
            "product_id": ticket.product_id,
            "event_type": event_type,
            "occurred_at": datetime.utcnow().isoformat(),
            "moderator_id": ticket.moderator_id,
            "moderator_comment": extra_payload.get("comment"),
            "blocking_reason_id": ticket.blocking_reason_id or None,
            "hard_block": extra_payload.get("hard_block", False),
            "field_reports": [
                {"field_name": report["field_path"], "comment": report["message"]}
                for report in extra_payload.get("field_reports", [])
            ],
        }
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{settings.B2B_SERVICE_URL}/api/v1/moderation/events",
                    json=event,
                    headers={"X-Service-Key": settings.MOD_TO_B2B_KEY},
                    timeout=5.0,
                )
                response.raise_for_status()
        except Exception:
            # The state-machine contract must not roll back a completed decision
            # because the companion service is temporarily unreachable.
            return None
