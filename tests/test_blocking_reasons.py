from datetime import datetime, timezone
from uuid import uuid4

from jose import jwt

from src.config import settings
from src.models.blocking_reason import BlockingReason
from src.models.product_moderation import ProductModeration


def admin_headers() -> dict:
    token = jwt.encode(
        {"sub": str(uuid4()), "role": "admin"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def uppercase_admin_headers() -> dict:
    token = jwt.encode(
        {"sub": str(uuid4()), "role": "ADMIN"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def moderator_headers() -> dict:
    token = jwt.encode(
        {"sub": str(uuid4()), "role": "moderator"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def create_reason(client, code="IMAGE_MISMATCH", hard_block=False):
    return client.post(
        "/api/v1/blocking-reasons",
        json={"code": code, "title": code.replace("_", " "), "hard_block": hard_block},
        headers=admin_headers(),
    )


def test_list_returns_active_reasons_with_required_code(client):
    created = create_reason(client)
    assert created.status_code == 201
    reason = created.json()
    assert reason["code"] == "IMAGE_MISMATCH"

    listed = client.get("/api/v1/blocking-reasons", headers=moderator_headers())
    assert listed.status_code == 200
    assert any(item["id"] == reason["id"] and item["code"] == "IMAGE_MISMATCH" for item in listed.json())


def test_inactive_reasons_are_hidden_and_patch_is_contract_method(client):
    reason = create_reason(client, code="BAD_DESCRIPTION").json()
    updated = client.patch(
        f"/api/v1/blocking-reasons/{reason['id']}",
        json={"is_active": False},
        headers=admin_headers(),
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False

    listed = client.get("/api/v1/blocking-reasons", headers=moderator_headers())
    assert reason["id"] not in [item["id"] for item in listed.json()]


def test_hard_block_filter_and_invalid_code_validation(client):
    hard_reason = create_reason(client, code="FORBIDDEN_GOODS_FILTER", hard_block=True)
    assert hard_reason.status_code == 201
    filtered = client.get("/api/v1/blocking-reasons?hard_block=true", headers=moderator_headers())
    assert all(item["hard_block"] is True for item in filtered.json())

    invalid = client.post(
        "/api/v1/blocking-reasons",
        json={"code": "bad-code", "title": "Bad", "hard_block": False},
        headers=admin_headers(),
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "VALIDATION_ERROR"


def test_admin_operations_require_bearer_and_admin_role(client):
    body = {"code": "NO_AUTH", "title": "No auth", "hard_block": False}
    missing = client.post("/api/v1/blocking-reasons", json=body)
    assert missing.status_code == 401
    assert missing.json() == {"code": "UNAUTHORIZED", "message": "Missing or invalid authorization"}
    read_missing = client.get("/api/v1/blocking-reasons")
    assert read_missing.status_code == 401

    uppercase_admin = client.post(
        "/api/v1/blocking-reasons",
        json={**body, "code": "UPPERCASE_ADMIN"},
        headers=uppercase_admin_headers(),
    )
    assert uppercase_admin.status_code == 201

    forbidden = client.post("/api/v1/blocking-reasons", json={**body, "code": "NOT_ADMIN"}, headers=moderator_headers())
    assert forbidden.status_code == 403
    assert forbidden.json() == {"code": "FORBIDDEN", "message": "Administrator role is required"}


def test_referenced_reason_cannot_be_deactivated(client, db_session):
    reason = create_reason(client, code="COPYRIGHT").json()
    now = datetime.now(timezone.utc)
    db_session.add(
        ProductModeration(
            id=str(uuid4()),
            product_id=str(uuid4()),
            seller_id=str(uuid4()),
            status="BLOCKED",
            queue_priority=1,
            json_after={"skus": []},
            blocking_reason_id=reason["id"],
            date_created=now,
            date_updated=now,
        )
    )
    db_session.commit()

    response = client.delete(f"/api/v1/blocking-reasons/{reason['id']}", headers=admin_headers())
    assert response.status_code == 409
    assert response.json()["code"] == "REFERENCED_REASON"
