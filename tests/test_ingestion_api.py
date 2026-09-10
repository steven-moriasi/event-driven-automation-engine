import json
from datetime import UTC, datetime
from typing import cast

from fastapi.testclient import TestClient
from httpx import Response
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.models import AuditEvent, Delivery, InboundEvent, Subscription
from app.infrastructure.signing import sign_payload

OPERATOR_HEADERS = {
    "X-Actor-ID": "operator-1",
    "X-Actor-Roles": "operator",
}


def event_payload(
    *,
    event_id: str = "event-1",
    sequence: int | None = 1,
    data: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "id": event_id,
        "type": "order.created",
        "subject": "order-42",
        "occurred_at": datetime(2025, 1, 1, tzinfo=UTC).isoformat(),
        "sequence": sequence,
        "data": data or {"reference": "PO-42"},
        "metadata": {"tenant": "example"},
    }


def create_subscription(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/subscriptions",
        headers=OPERATOR_HEADERS,
        json={
            "name": "Order consumer",
            "event_type": "order.created",
            "adapter_type": "generic_webhook",
            "endpoint_url": "https://consumer.example/events",
        },
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def post_event(
    client: TestClient,
    payload: dict[str, object],
    signature: str | None = None,
) -> Response:
    body = json.dumps(payload, separators=(",", ":")).encode()
    return client.post(
        "/webhooks/partner",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Event-Signature": signature
            or sign_payload(body, secret_value("webhook-secret")),
            "X-Correlation-ID": "correlation-1",
        },
    )


def secret_value(value: str) -> SecretStr:
    return SecretStr(value)


def test_signed_ingestion_is_transactional_and_idempotent(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    subscription = create_subscription(client)
    payload = event_payload()

    accepted = post_event(client, payload)
    assert accepted.status_code == 202
    assert accepted.json()["duplicate"] is False
    assert accepted.json()["delivery_count"] == 1

    duplicate = post_event(client, payload)
    assert duplicate.status_code == 202
    assert duplicate.json()["duplicate"] is True
    assert duplicate.json()["id"] == accepted.json()["id"]

    with session_factory() as session:
        assert session.scalar(select(func.count(InboundEvent.id))) == 1
        assert session.scalar(select(func.count(Delivery.id))) == 1
        assert session.scalar(select(func.count(AuditEvent.id))) == 2
        delivery = session.scalar(select(Delivery))
        assert delivery is not None
        assert delivery.subscription_id == subscription["id"]


def test_reused_event_identifier_with_new_payload_conflicts(
    client: TestClient,
) -> None:
    create_subscription(client)
    assert post_event(client, event_payload()).status_code == 202

    conflict = post_event(
        client,
        event_payload(data={"reference": "PO-DIFFERENT"}),
    )

    assert conflict.status_code == 409
    assert conflict.json()["detail"] == (
        "Event identifier was reused with a different payload"
    )


def test_webhook_rejects_invalid_signatures_sources_and_envelopes(
    client: TestClient,
) -> None:
    invalid_signature = post_event(
        client,
        event_payload(),
        signature="sha256=invalid",
    )
    assert invalid_signature.status_code == 401

    unknown_source = client.post(
        "/webhooks/unknown",
        content=b"{}",
        headers={"X-Event-Signature": "sha256=invalid"},
    )
    assert unknown_source.status_code == 404

    invalid_body = b'{"id":"missing-required-fields"}'
    invalid_envelope = client.post(
        "/webhooks/partner",
        content=invalid_body,
        headers={
            "Content-Type": "application/json",
            "X-Event-Signature": sign_payload(
                invalid_body,
                secret_value("webhook-secret"),
            ),
        },
    )
    assert invalid_envelope.status_code == 422


def test_subscription_creation_requires_operator_role(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    body = {
        "name": "Unauthorized",
        "event_type": "order.created",
        "adapter_type": "generic_webhook",
        "endpoint_url": "https://consumer.example/events",
    }
    missing_actor = client.post("/subscriptions", json=body)
    viewer = client.post(
        "/subscriptions",
        headers={"X-Actor-ID": "viewer-1", "X-Actor-Roles": "viewer"},
        json=body,
    )

    assert missing_actor.status_code == 401
    assert viewer.status_code == 403
    with session_factory() as session:
        assert session.scalar(select(func.count(Subscription.id))) == 0
