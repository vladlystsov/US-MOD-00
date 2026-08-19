from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.models.product_moderation import ProductModeration


def moderator_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def ticket(product_id: str, priority: int, created_at: datetime, status: str = "PENDING", moderator_id: str | None = None):
    return ProductModeration(
        id=str(uuid4()),
        product_id=product_id,
        seller_id=str(uuid4()),
        status=status,
        queue_priority=priority,
        json_after={"id": product_id, "skus": [{"id": "sku"}]},
        moderator_id=moderator_id,
        date_created=created_at,
        date_updated=created_at,
    )


def test_next_returns_oldest_pending_as_ticket_response(client, db_session, valid_jwt_with_fixed_id):
    token, moderator_id = valid_jwt_with_fixed_id
    db_session.query(ProductModeration).delete()
    first = ticket("product-1", 1, datetime(2026, 1, 1, tzinfo=timezone.utc))
    second = ticket("product-2", 1, datetime(2026, 1, 2, tzinfo=timezone.utc))
    db_session.add_all([first, second])
    db_session.commit()

    response = client.post("/api/v1/queue/claim", headers=moderator_headers(token))

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == first.id
    assert data["product_id"] == "product-1"
    assert data["kind"] == "CREATE"
    assert data["status"] == "IN_REVIEW"
    assert data["assigned_moderator_id"] == moderator_id
    assert data["created_at"]


def test_empty_queue_returns_204_without_body(client, db_session, valid_jwt):
    db_session.query(ProductModeration).delete()
    db_session.commit()

    response = client.post("/api/v1/queue/claim", headers=moderator_headers(valid_jwt))
    assert response.status_code == 204
    assert response.content == b""


def test_invalid_queue_priority_returns_400(client, valid_jwt):
    response = client.post(
        "/api/v1/queue/claim", json={"queue_priority": 5}, headers=moderator_headers(valid_jwt)
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_QUEUE"


def test_autoprioritization_uses_priority_then_fifo(client, db_session, valid_jwt):
    db_session.query(ProductModeration).delete()
    older_lower_priority = ticket("product-4", 4, datetime(2026, 1, 1, tzinfo=timezone.utc))
    later_higher_priority = ticket("product-1", 1, datetime(2026, 1, 2, tzinfo=timezone.utc))
    db_session.add_all([older_lower_priority, later_higher_priority])
    db_session.commit()

    response = client.post("/api/v1/queue/claim", headers=moderator_headers(valid_jwt))
    assert response.status_code == 200
    assert response.json()["product_id"] == "product-1"


def test_expired_claim_is_returned_to_pending_and_can_be_reclaimed(client, db_session, valid_jwt_with_fixed_id):
    token, moderator_id = valid_jwt_with_fixed_id
    expired = ticket("expired", 1, datetime(2026, 1, 1, tzinfo=timezone.utc), "IN_REVIEW", moderator_id)
    expired.claimed_at = datetime.utcnow() - timedelta(hours=1)
    expired.claim_expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.add(expired)
    db_session.commit()

    response = client.post("/api/v1/queue/claim", headers=moderator_headers(token))

    assert response.status_code == 200
    assert response.json()["id"] == expired.id
    assert response.json()["status"] == "IN_REVIEW"
    assert response.json()["assigned_moderator_id"] == moderator_id


def test_moderator_already_has_in_review_returns_409(client, db_session, valid_jwt_with_fixed_id):
    token, moderator_id = valid_jwt_with_fixed_id
    db_session.add(ticket("locked", 1, datetime(2026, 1, 1, tzinfo=timezone.utc), "IN_REVIEW", moderator_id))
    db_session.add(ticket("pending", 1, datetime(2026, 1, 2, tzinfo=timezone.utc)))
    db_session.commit()

    response = client.post("/api/v1/queue/claim", headers=moderator_headers(token))
    assert response.status_code == 409
    assert response.json()["code"] == "MODERATOR_BUSY"
