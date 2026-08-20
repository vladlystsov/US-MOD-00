import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import httpx

from src.models.product_moderation import ProductModeration
from src.config import settings


MOCK_B2B_PRODUCT = {
    "id": "product-1",
    "title": "iPhone 15",
    "description": "Smartphone",
    "status": "ON_MODERATION",
    "deleted": False,
    "blocked": False,
    "category": {"id": "cat-1", "name": "Electronics"},
    "images": [],
    "characteristics": [],
    "skus": [
        {
            "id": "sku-1",
            "name": "256GB Black",
            "price": 12999000,
            "active_quantity": 10,
            "image": "/s3/iphone.jpg",
            "characteristics": []
        }
    ]
}


class TestProductEvents:

    @patch('src.services.event_service.httpx.Client')
    def test_created_pending(self, MockClient, client, db_session):
        """CREATED event creates card in PENDING status"""
        db_session.query(ProductModeration).delete()
        db_session.commit()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_B2B_PRODUCT
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client_instance

        response = client.post(
            "/api/v1/events/product",
            json={
                "product_id": "product-1",
                "seller_id": str(uuid4()),
                "event": "CREATED",
                "date": datetime.now(timezone.utc).isoformat()
            },
            headers={"X-Service-Key": settings.B2B_SERVICE_KEY}
        )

        assert response.status_code == 200
        assert response.json()["accepted"] is True

        moderation = db_session.query(ProductModeration).filter(
            ProductModeration.product_id == "product-1"
        ).first()
        assert moderation is not None
        assert moderation.status == "PENDING"
        assert moderation.json_after is not None

    @patch('src.services.event_service.httpx.Client')
    def test_edited_returns_to_review(self, MockClient, client, db_session):
        """EDITED after MODERATED returns card to queue"""
        db_session.query(ProductModeration).delete()
        db_session.commit()

        moderation = ProductModeration(
            id=str(uuid4()),
            product_id="product-2",
            seller_id=str(uuid4()),
            status="MODERATED",
            queue_priority=1,
            json_after=MOCK_B2B_PRODUCT
        )
        db_session.add(moderation)
        db_session.commit()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_B2B_PRODUCT
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client_instance

        response = client.post(
            "/api/v1/events/product",
            json={
                "product_id": "product-2",
                "seller_id": str(uuid4()),
                "event": "EDITED",
                "date": datetime.now(timezone.utc).isoformat()
            },
            headers={"X-Service-Key": settings.B2B_SERVICE_KEY}
        )

        assert response.status_code == 200
        db_session.refresh(moderation)
        assert moderation.status == "PENDING"

    @patch('src.services.event_service.httpx.Client')
    def test_edited_updates_in_review(self, MockClient, client, db_session):
        """EDITED during IN_REVIEW updates fields"""
        db_session.query(ProductModeration).delete()
        db_session.commit()

        moderation = ProductModeration(
            id=str(uuid4()),
            product_id="product-3",
            seller_id=str(uuid4()),
            status="IN_REVIEW",
            queue_priority=1,
            json_after=MOCK_B2B_PRODUCT
        )
        db_session.add(moderation)
        db_session.commit()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_B2B_PRODUCT
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client_instance

        response = client.post(
            "/api/v1/events/product",
            json={
                "product_id": "product-3",
                "seller_id": str(uuid4()),
                "event": "EDITED",
                "date": datetime.now(timezone.utc).isoformat()
            },
            headers={"X-Service-Key": settings.B2B_SERVICE_KEY}
        )

        assert response.status_code == 200
        db_session.refresh(moderation)
        assert moderation.status == "PENDING"

    @patch('src.services.event_service.httpx.Client')
    def test_deleted_archived(self, MockClient, client, db_session):
        """DELETED archives the card"""
        db_session.query(ProductModeration).delete()
        db_session.commit()

        moderation = ProductModeration(
            id=str(uuid4()),
            product_id="product-4",
            seller_id=str(uuid4()),
            status="PENDING",
            queue_priority=1,
            json_after=MOCK_B2B_PRODUCT
        )
        db_session.add(moderation)
        db_session.commit()

        response = client.post(
            "/api/v1/events/product",
            json={
                "product_id": "product-4",
                "seller_id": str(uuid4()),
                "event": "DELETED",
                "date": datetime.now(timezone.utc).isoformat()
            },
            headers={"X-Service-Key": settings.B2B_SERVICE_KEY}
        )

        assert response.status_code == 200
        moderation_check = db_session.query(ProductModeration).filter(
            ProductModeration.product_id == "product-4"
        ).first()
        assert moderation_check is None

    @patch('src.services.event_service.httpx.Client')
    def test_duplicate_event_no_side_effects(self, MockClient, client, db_session):
        """Duplicate event → 200, no changes"""
        db_session.query(ProductModeration).delete()
        db_session.commit()

        moderation = ProductModeration(
            id=str(uuid4()),
            product_id="product-5",
            seller_id=str(uuid4()),
            status="PENDING",
            queue_priority=1,
            json_after=MOCK_B2B_PRODUCT
        )
        db_session.add(moderation)
        db_session.commit()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_B2B_PRODUCT
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client_instance

        response1 = client.post(
            "/api/v1/events/product",
            json={
                "product_id": "product-5",
                "seller_id": str(uuid4()),
                "event": "CREATED",
                "date": datetime.now(timezone.utc).isoformat()
            },
            headers={"X-Service-Key": settings.B2B_SERVICE_KEY}
        )
        assert response1.status_code == 200

        response2 = client.post(
            "/api/v1/events/product",
            json={
                "product_id": "product-5",
                "seller_id": str(uuid4()),
                "event": "CREATED",
                "date": datetime.now(timezone.utc).isoformat()
            },
            headers={"X-Service-Key": settings.B2B_SERVICE_KEY}
        )
        assert response2.status_code == 200

    def test_missing_service_header_401(self, client):
        """No X-Service-Key → 401"""
        response = client.post(
            "/api/v1/events/product",
            json={
                "product_id": str(uuid4()),
                "seller_id": str(uuid4()),
                "event": "CREATED",
                "date": datetime.now(timezone.utc).isoformat()
            }
        )
        assert response.status_code == 401


def test_b2b_event_envelope_deletes_existing_ticket(client, db_session):
    product_id = str(uuid4())
    moderation = ProductModeration(
        id=str(uuid4()),
        product_id=product_id,
        seller_id=str(uuid4()),
        status="PENDING",
        queue_priority=1,
        json_after=MOCK_B2B_PRODUCT,
    )
    db_session.add(moderation)
    db_session.commit()

    response = client.post(
        "/api/v1/b2b/events",
        json={
            "event_type": "PRODUCT_DELETED",
            "idempotency_key": str(uuid4()),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {"product_id": product_id, "seller_id": moderation.seller_id},
        },
        headers={"X-Service-Key": settings.B2B_TO_MOD_KEY},
    )

    assert response.status_code == 202
    assert db_session.query(ProductModeration).filter(ProductModeration.product_id == product_id).first() is None


@patch('src.services.event_service.httpx.Client')
def test_duplicate_b2b_envelope_preserves_reclaimed_ticket(MockClient, client, db_session):
    product_id = str(uuid4())
    moderator_id = str(uuid4())
    ticket = ProductModeration(
        id=str(uuid4()),
        product_id=product_id,
        seller_id=str(uuid4()),
        status="IN_REVIEW",
        queue_priority=1,
        moderator_id=moderator_id,
        json_after=MOCK_B2B_PRODUCT,
    )
    db_session.add(ticket)
    db_session.commit()

    response = MagicMock()
    response.json.return_value = MOCK_B2B_PRODUCT
    response.raise_for_status = MagicMock()
    http_client = MagicMock()
    http_client.get.return_value = response
    http_client.__enter__.return_value = http_client
    http_client.__exit__.return_value = False
    MockClient.return_value = http_client

    event = {
        "event_type": "PRODUCT_EDITED",
        "idempotency_key": str(uuid4()),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {"product_id": product_id, "seller_id": ticket.seller_id},
    }
    headers = {"X-Service-Key": settings.B2B_TO_MOD_KEY}

    first = client.post("/api/v1/b2b/events", json=event, headers=headers)
    assert first.status_code == 202
    db_session.refresh(ticket)
    ticket.status = "IN_REVIEW"
    ticket.moderator_id = moderator_id
    db_session.commit()

    duplicate = client.post("/api/v1/b2b/events", json=event, headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "DUPLICATE_EVENT"
    db_session.refresh(ticket)
    assert ticket.status == "IN_REVIEW"
    assert ticket.moderator_id == moderator_id
