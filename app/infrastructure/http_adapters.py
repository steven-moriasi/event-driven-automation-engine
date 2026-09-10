import json

import httpx

from app.core.config import Settings
from app.core.metrics import DELIVERY_ATTEMPTS, DELIVERY_DURATION
from app.domain.enums import AdapterType
from app.domain.models import InboundEvent, Subscription
from app.infrastructure.signing import sign_payload
from app.services.adapters import DeliveryAdapter, DeliveryResult


class HttpDeliveryAdapter:
    def __init__(
        self,
        *,
        adapter_type: AdapterType,
        settings: Settings,
        client: httpx.Client,
    ) -> None:
        self.adapter_type = adapter_type
        self.settings = settings
        self.client = client

    def deliver(
        self,
        event: InboundEvent,
        subscription: Subscription,
        idempotency_key: str,
    ) -> DeliveryResult:
        prepared = self._prepare(event, idempotency_key)
        if isinstance(prepared, DeliveryResult):
            return prepared
        body, headers = prepared
        try:
            with DELIVERY_DURATION.labels(adapter=self.adapter_type.value).time():
                response = self.client.post(
                    subscription.endpoint_url,
                    content=body,
                    headers=headers,
                )
        except httpx.HTTPError:
            result = DeliveryResult(
                succeeded=False,
                transient=True,
                status_code=None,
                error_code="integration_unavailable",
                error_message="Integration request did not complete",
            )
        else:
            result = classify_response(response.status_code)
        outcome = (
            "succeeded"
            if result.succeeded
            else "transient_failure"
            if result.transient
            else "permanent_failure"
        )
        DELIVERY_ATTEMPTS.labels(adapter=self.adapter_type.value, outcome=outcome).inc()
        return result

    def _prepare(
        self,
        event: InboundEvent,
        idempotency_key: str,
    ) -> tuple[bytes, dict[str, str]] | DeliveryResult:
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
            "User-Agent": "event-driven-automation-engine/0.1",
        }
        if self.adapter_type == AdapterType.GENERIC_WEBHOOK:
            if self.settings.delivery_signing_secret is None:
                return configuration_error("delivery_signing_secret")
            body = canonical_json(event.payload)
            headers["X-Event-Signature"] = sign_payload(
                body,
                self.settings.delivery_signing_secret,
            )
            return body, headers
        if self.adapter_type == AdapterType.GITHUB_ISSUES:
            if self.settings.github_token is None:
                return configuration_error("github_token")
            data = event.payload.get("data")
            if not isinstance(data, dict):
                return mapping_error()
            title = data.get("title")
            issue_body = data.get("body")
            if not isinstance(title, str) or not isinstance(issue_body, str):
                return mapping_error()
            headers["Authorization"] = (
                f"Bearer {self.settings.github_token.get_secret_value()}"
            )
            headers["Accept"] = "application/vnd.github+json"
            return canonical_json({"title": title, "body": issue_body}), headers
        data = event.payload.get("data")
        if not isinstance(data, dict):
            return mapping_error()
        text = data.get("text")
        if not isinstance(text, str):
            return mapping_error()
        return canonical_json({"text": text}), headers


class AdapterRegistry:
    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or httpx.Client(timeout=10, follow_redirects=False)

    def for_type(self, adapter_type: AdapterType) -> DeliveryAdapter:
        return HttpDeliveryAdapter(
            adapter_type=adapter_type,
            settings=self.settings,
            client=self.client,
        )


def canonical_json(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def classify_response(status_code: int) -> DeliveryResult:
    if 200 <= status_code < 300:
        return DeliveryResult(succeeded=True, transient=False, status_code=status_code)
    if status_code in {408, 425, 429} or status_code >= 500:
        return DeliveryResult(
            succeeded=False,
            transient=True,
            status_code=status_code,
            error_code="integration_transient_failure",
            error_message="Integration returned a retryable response",
        )
    return DeliveryResult(
        succeeded=False,
        transient=False,
        status_code=status_code,
        error_code="integration_permanent_failure",
        error_message="Integration rejected the delivery",
    )


def configuration_error(setting: str) -> DeliveryResult:
    return DeliveryResult(
        succeeded=False,
        transient=False,
        status_code=None,
        error_code="integration_not_configured",
        error_message=f"Required integration setting is missing: {setting}",
    )


def mapping_error() -> DeliveryResult:
    return DeliveryResult(
        succeeded=False,
        transient=False,
        status_code=None,
        error_code="integration_mapping_invalid",
        error_message="Event data does not satisfy the adapter contract",
    )
