import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.enums import EventStatus
from app.domain.models import Delivery, InboundEvent, Subscription
from app.domain.schemas import EventEnvelope, EventResponse
from app.services.audit import append_audit


class IdempotencyConflictError(ValueError):
    pass


def canonical_payload(envelope: EventEnvelope) -> bytes:
    payload = envelope.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def payload_digest(envelope: EventEnvelope) -> str:
    return hashlib.sha256(canonical_payload(envelope)).hexdigest()


def ingest_event(
    session: Session,
    *,
    source: str,
    envelope: EventEnvelope,
    correlation_id: str,
) -> EventResponse:
    digest = payload_digest(envelope)
    event = InboundEvent(
        source=source,
        external_id=envelope.id,
        event_type=envelope.type,
        subject=envelope.subject,
        sequence=envelope.sequence,
        occurred_at=envelope.occurred_at,
        payload=envelope.model_dump(mode="json"),
        payload_hash=digest,
        correlation_id=correlation_id,
    )
    session.add(event)
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        existing = session.scalar(
            select(InboundEvent).where(
                InboundEvent.source == source,
                InboundEvent.external_id == envelope.id,
            )
        )
        if existing is None:
            raise
        if existing.payload_hash != digest:
            raise IdempotencyConflictError(
                "Event identifier was reused with a different payload"
            ) from error
        delivery_count = session.scalar(
            select(func.count())
            .select_from(Delivery)
            .where(Delivery.event_id == existing.id)
        )
        return event_response(existing, duplicate=True, delivery_count=delivery_count or 0)

    subscriptions = session.scalars(
        select(Subscription).where(
            Subscription.enabled.is_(True),
            Subscription.event_type == envelope.type,
        )
    ).all()
    for subscription in subscriptions:
        session.add(
            Delivery(
                event_id=event.id,
                subscription_id=subscription.id,
                idempotency_key=f"{source}:{envelope.id}:{subscription.id}",
            )
        )
    if subscriptions:
        event.status = EventStatus.DISPATCHED
    append_audit(
        session,
        aggregate_type="event",
        aggregate_id=event.id,
        action="event_ingested",
        actor=f"webhook:{source}",
        correlation_id=correlation_id,
        details={"delivery_count": len(subscriptions)},
    )
    session.commit()
    return event_response(
        event,
        duplicate=False,
        delivery_count=len(subscriptions),
    )


def event_response(
    event: InboundEvent,
    *,
    duplicate: bool,
    delivery_count: int,
) -> EventResponse:
    return EventResponse(
        id=event.id,
        external_id=event.external_id,
        source=event.source,
        event_type=event.event_type,
        subject=event.subject,
        sequence=event.sequence,
        status=event.status,
        duplicate=duplicate,
        delivery_count=delivery_count,
        correlation_id=event.correlation_id,
    )
