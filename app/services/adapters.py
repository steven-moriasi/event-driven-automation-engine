from dataclasses import dataclass
from typing import Protocol

from app.domain.models import InboundEvent, Subscription


@dataclass(frozen=True)
class DeliveryResult:
    succeeded: bool
    transient: bool
    status_code: int | None
    error_code: str | None = None
    error_message: str | None = None


class DeliveryAdapter(Protocol):
    def deliver(
        self,
        event: InboundEvent,
        subscription: Subscription,
        idempotency_key: str,
    ) -> DeliveryResult: ...
