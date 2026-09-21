from datetime import UTC, datetime
from typing import Protocol, cast

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.domain.enums import DeliveryStatus
from app.domain.models import Delivery
from app.infrastructure.auth import Actor
from app.services.audit import append_audit


class _RowCountResult(Protocol):
    rowcount: int


def utc_now() -> datetime:
    return datetime.now(UTC)


def recover_expired_deliveries(
    session: Session,
    *,
    actor: str,
    now: datetime | None = None,
) -> int:
    recovered_at = now or utc_now()
    expired = cast(
        _RowCountResult,
        session.execute(
            update(Delivery)
            .where(
                Delivery.status == DeliveryStatus.DELIVERING,
                Delivery.lease_expires_at < recovered_at,
            )
            .values(
                status=DeliveryStatus.PENDING,
                worker_id=None,
                lease_expires_at=None,
                available_at=recovered_at,
                error_code="delivery_lease_expired",
                error_message="Delivery lease expired before acknowledgement",
            )
            .execution_options(synchronize_session=False)
        )
    )
    if expired.rowcount:
        append_audit(
            session,
            aggregate_type="system",
            aggregate_id="delivery-recovery",
            action="delivery_leases_recovered",
            actor=actor,
            correlation_id=f"recovery:{recovered_at.isoformat()}",
            details={"count": expired.rowcount},
        )
    session.commit()
    return expired.rowcount


def replay_dead_delivery(
    session: Session,
    *,
    delivery: Delivery,
    actor: Actor,
    reason: str,
    correlation_id: str,
    now: datetime | None = None,
) -> Delivery | None:
    replayed_at = now or utc_now()
    replayed = cast(
        _RowCountResult,
        session.execute(
            update(Delivery)
            .where(
                Delivery.id == delivery.id,
                Delivery.status == DeliveryStatus.DEAD,
                Delivery.fencing_token == delivery.fencing_token,
            )
            .values(
                status=DeliveryStatus.PENDING,
                attempts=0,
                replay_count=delivery.replay_count + 1,
                fencing_token=delivery.fencing_token + 1,
                available_at=replayed_at,
                worker_id=None,
                lease_expires_at=None,
                delivered_at=None,
                response_code=None,
                error_code=None,
                error_message=None,
                last_replayed_at=replayed_at,
            )
            .execution_options(synchronize_session=False)
        )
    )
    if replayed.rowcount != 1:
        session.rollback()
        return None
    append_audit(
        session,
        aggregate_type="delivery",
        aggregate_id=delivery.id,
        action="delivery_replayed",
        actor=actor.id,
        correlation_id=correlation_id,
        details={"reason": reason, "replay_count": delivery.replay_count + 1},
    )
    session.commit()
    return session.get(Delivery, delivery.id, populate_existing=True)
