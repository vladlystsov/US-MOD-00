from datetime import datetime, timezone
from uuid import uuid4

from src.models.blocking_reason import BlockingReason
from src.models.product_moderation import ProductModeration
from src.services import ticket_service


class _Response:
    def raise_for_status(self):
        return None


class _Client:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _Response()


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def in_review_ticket(moderator_id: str, skus=True) -> ProductModeration:
    now = datetime.now(timezone.utc)
    return ProductModeration(
        id=str(uuid4()),
        product_id=str(uuid4()),
        seller_id=str(uuid4()),
        status="IN_REVIEW",
        queue_priority=1,
        moderator_id=moderator_id,
        json_after={"skus": [{"id": "sku"}]} if skus else {"skus": []},
        date_created=now,
        date_updated=now,
    )


def test_approve_reads_contract_comment_and_emits_moderated_event(client, db_session, valid_jwt_with_fixed_id, monkeypatch):
    token, moderator_id = valid_jwt_with_fixed_id
    card = in_review_ticket(moderator_id)
    db_session.add(card)
    db_session.commit()
    calls = []
    monkeypatch.setattr(ticket_service.httpx, "Client", lambda: _Client(calls))

    response = client.post(f"/api/v1/tickets/{card.id}/approve", json={"comment": "Looks good"}, headers=headers(token))

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"
    db_session.refresh(card)
    assert card.moderator_comment == "Looks good"
    assert calls[0][1]["json"]["event_type"] == "MODERATED"
    assert calls[0][1]["json"]["payload"]["comment"] == "Looks good"


def test_approve_others_ticket_returns_contract_409(client, db_session, valid_jwt_with_fixed_id):
    token, _ = valid_jwt_with_fixed_id
    card = in_review_ticket(str(uuid4()))
    db_session.add(card)
    db_session.commit()

    response = client.post(f"/api/v1/tickets/{card.id}/approve", headers=headers(token))
    assert response.status_code == 409
    assert response.json()["code"] == "TICKET_NOT_ASSIGNED"


def test_approve_without_sku_returns_409(client, db_session, valid_jwt_with_fixed_id):
    token, moderator_id = valid_jwt_with_fixed_id
    card = in_review_ticket(moderator_id, skus=False)
    db_session.add(card)
    db_session.commit()

    response = client.post(f"/api/v1/tickets/{card.id}/approve", headers=headers(token))
    assert response.status_code == 409
    assert response.json()["code"] == "NO_SKUS"


def test_hard_block_reads_comment_and_emits_true_flag(client, db_session, valid_jwt_with_fixed_id, monkeypatch):
    token, moderator_id = valid_jwt_with_fixed_id
    reason = BlockingReason(code="FORBIDDEN_GOODS", title="Forbidden", hard_block=True, is_active=True)
    card = in_review_ticket(moderator_id)
    db_session.add_all([reason, card])
    db_session.commit()
    calls = []
    monkeypatch.setattr(ticket_service.httpx, "Client", lambda: _Client(calls))

    response = client.post(
        f"/api/v1/tickets/{card.id}/block",
        json={"blocking_reason_ids": [reason.id], "comment": "Counterfeit"},
        headers=headers(token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "HARD_BLOCKED"
    db_session.refresh(card)
    assert card.moderator_comment == "Counterfeit"
    assert calls[0][1]["json"]["event_type"] == "BLOCKED"
    assert calls[0][1]["json"]["payload"]["hard_block"] is True


def test_any_modify_on_hard_blocked_returns_403(client, db_session, valid_jwt_with_fixed_id):
    token, moderator_id = valid_jwt_with_fixed_id
    card = in_review_ticket(moderator_id)
    card.status = "HARD_BLOCKED"
    db_session.add(card)
    db_session.commit()

    response = client.post(f"/api/v1/tickets/{card.id}/approve", headers=headers(token))
    assert response.status_code == 403
