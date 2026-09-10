import json
from datetime import UTC, datetime

import httpx
import pytest

from app.core.config import Settings
from app.domain.enums import AdapterType, EventStatus
from app.domain.models import InboundEvent, Subscription
from app.infrastructure.http_adapters import (
    HttpDeliveryAdapter,
    classify_response,
)
from app.infrastructure.signing import verify_signature


def make_event(data: dict[str, str]) -> InboundEvent:
    occurred_at = datetime(2025, 1, 1, tzinfo=UTC)
    return InboundEvent(
        id="event-1",
        source="partner",
        external_id="external-1",
        event_type="order.created",
        subject="order-42",
        sequence=1,
        occurred_at=occurred_at,
        received_at=occurred_at,
        payload={
            "id": "external-1",
            "type": "order.created",
            "subject": "order-42",
            "occurred_at": occurred_at.isoformat(),
            "sequence": 1,
            "data": data,
            "metadata": {},
        },
        payload_hash="0" * 64,
        status=EventStatus.DISPATCHED,
        correlation_id="correlation-1",
    )


def make_subscription(adapter_type: AdapterType) -> Subscription:
    return Subscription(
        id="subscription-1",
        name=f"{adapter_type.value} consumer",
        event_type="order.created",
        adapter_type=adapter_type,
        endpoint_url="https://integration.example/deliver",
    )


def test_generic_webhook_is_signed_and_idempotent(settings: Settings) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(202)

    adapter = HttpDeliveryAdapter(
        adapter_type=AdapterType.GENERIC_WEBHOOK,
        settings=settings,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    event = make_event({"reference": "PO-42"})
    result = adapter.deliver(
        event,
        make_subscription(AdapterType.GENERIC_WEBHOOK),
        "delivery-key",
    )

    assert result.succeeded
    assert len(captured) == 1
    request = captured[0]
    assert request.headers["Idempotency-Key"] == "delivery-key"
    assert json.loads(request.content) == event.payload
    assert settings.delivery_signing_secret is not None
    assert verify_signature(
        request.content,
        request.headers["X-Event-Signature"],
        settings.delivery_signing_secret,
    )


@pytest.mark.parametrize(
    ("adapter_type", "data", "expected_body"),
    [
        (
            AdapterType.GITHUB_ISSUES,
            {"title": "Order failed", "body": "Review order 42"},
            {"title": "Order failed", "body": "Review order 42"},
        ),
        (
            AdapterType.SLACK_WEBHOOK,
            {"text": "Order 42 requires attention"},
            {"text": "Order 42 requires attention"},
        ),
    ],
)
def test_public_api_adapters_map_bounded_payloads(
    settings: Settings,
    adapter_type: AdapterType,
    data: dict[str, str],
    expected_body: dict[str, str],
) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200)

    adapter = HttpDeliveryAdapter(
        adapter_type=adapter_type,
        settings=settings,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = adapter.deliver(
        make_event(data),
        make_subscription(adapter_type),
        "delivery-key",
    )

    assert result.succeeded
    assert json.loads(captured[0].content) == expected_body
    if adapter_type == AdapterType.GITHUB_ISSUES:
        assert captured[0].headers["Authorization"] == "Bearer github-token"
        assert captured[0].headers["Accept"] == "application/vnd.github+json"
    else:
        assert "Authorization" not in captured[0].headers


@pytest.mark.parametrize(
    ("status_code", "succeeded", "transient", "error_code"),
    [
        (204, True, False, None),
        (408, False, True, "integration_transient_failure"),
        (429, False, True, "integration_transient_failure"),
        (503, False, True, "integration_transient_failure"),
        (400, False, False, "integration_permanent_failure"),
    ],
)
def test_http_statuses_are_classified_for_retry(
    status_code: int,
    succeeded: bool,
    transient: bool,
    error_code: str | None,
) -> None:
    result = classify_response(status_code)

    assert result.succeeded is succeeded
    assert result.transient is transient
    assert result.error_code == error_code


def test_network_and_mapping_failures_do_not_expose_provider_details(
    settings: Settings,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "provider response contained private-token",
            request=request,
        )

    network_adapter = HttpDeliveryAdapter(
        adapter_type=AdapterType.GENERIC_WEBHOOK,
        settings=settings,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    network_result = network_adapter.deliver(
        make_event({"reference": "PO-42"}),
        make_subscription(AdapterType.GENERIC_WEBHOOK),
        "delivery-key",
    )
    assert network_result.transient
    assert network_result.error_code == "integration_unavailable"
    assert network_result.error_message == "Integration request did not complete"
    assert "private-token" not in network_result.error_message

    mapping_adapter = HttpDeliveryAdapter(
        adapter_type=AdapterType.GITHUB_ISSUES,
        settings=settings,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    mapping_result = mapping_adapter.deliver(
        make_event({"title": "Missing body"}),
        make_subscription(AdapterType.GITHUB_ISSUES),
        "delivery-key",
    )
    assert not mapping_result.transient
    assert mapping_result.error_code == "integration_mapping_invalid"


def test_missing_adapter_credentials_fail_without_network_access() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, request=request)

    settings = Settings(
        database_url="sqlite://",
        delivery_signing_secret=None,
        github_token=None,
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))

    generic = HttpDeliveryAdapter(
        adapter_type=AdapterType.GENERIC_WEBHOOK,
        settings=settings,
        client=client,
    ).deliver(
        make_event({"reference": "PO-42"}),
        make_subscription(AdapterType.GENERIC_WEBHOOK),
        "delivery-key",
    )
    github = HttpDeliveryAdapter(
        adapter_type=AdapterType.GITHUB_ISSUES,
        settings=settings,
        client=client,
    ).deliver(
        make_event({"title": "Title", "body": "Body"}),
        make_subscription(AdapterType.GITHUB_ISSUES),
        "delivery-key",
    )

    assert generic.error_code == "integration_not_configured"
    assert github.error_code == "integration_not_configured"
    assert calls == 0
