import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, and_, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain.enums import DeliveryStatus
from app.domain.models import ConsumerCheckpoint, Delivery, InboundEvent, Subscription
from app.services.adapters import DeliveryAdapter, DeliveryResult
from app.services.audit import append_audit


def utc_now() -> datetime:
    return datetime.now(UTC)


def claimable_delivery(now: datetime) -> Select[tuple[Delivery]]:
    return (
        select(Delivery)
        .where(
            or_(
                and_(
                    Delivery.status.in_(
                        [DeliveryStatus.PENDING, DeliveryStatus.BLOCKED]
                    ),
                    Delivery.available_at <= now,
                ),
                and_(
                    Delivery.status == DeliveryStatus.DELIVERING,
                    Delivery.lease_expires_at < now,
                ),
            )
        )
        .order_by(Delivery.available_at, Delivery.created_at)
        .limit(1)
    )


def claim_next_delivery(
    session: Session,
    *,
    worker_id: str,
    lease_seconds: int,
    now: datetime | None = None,
) -> Delivery | None:
    claimed_at = now or utc_now()
    candidate = session.scalar(claimable_delivery(claimed_at))
    if candidate is None:
        return None
    previous_status = candidate.status
    previous_token = candidate.fencing_token
    condition = [
        Delivery.id == candidate.id,
        Delivery.status == previous_status,
        Delivery.fencing_token == previous_token,
    ]
    if previous_status == DeliveryStatus.DELIVERING:
        condition.append(Delivery.lease_expires_at < claimed_at)
    else:
        condition.append(Delivery.available_at <= claimed_at)
    claimed = session.execute(
        update(Delivery)
        .where(*condition)
        .values(
            status=DeliveryStatus.DELIVERING,
            worker_id=worker_id,
            lease_expires_at=claimed_at + timedelta(seconds=lease_seconds),
            fencing_token=previous_token + 1,
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    if claimed.rowcount != 1:
        return None
    return session.get(Delivery, candidate.id, populate_existing=True)


class DeliveryProcessor:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def process(
        self,
        delivery: Delivery,
        *,
        worker_id: str,
        adapter: DeliveryAdapter,
        now: datetime | None = None,
    ) -> bool:
        processed_at = now or utc_now()
        if not self._owns_lease(delivery, worker_id, processed_at):
            self.session.rollback()
            return False
        event = self.session.get(InboundEvent, delivery.event_id)
        subscription = self.session.get(Subscription, delivery.subscription_id)
        if event is None or subscription is None:
            return self._record_result(
                delivery,
                worker_id=worker_id,
                result=DeliveryResult(
                    succeeded=False,
                    transient=False,
                    status_code=None,
                    error_code="delivery_target_missing",
                    error_message="Delivery dependencies are unavailable",
                ),
                processed_at=processed_at,
            )
        ordering_result = self._check_order(event, subscription, delivery, processed_at)
        if ordering_result is not None:
            return ordering_result
        result = adapter.deliver(event, subscription, delivery.idempotency_key)
        advances_checkpoint = result.succeeded and event.sequence is not None
        finalized = self._record_result(
            delivery,
            worker_id=worker_id,
            result=result,
            processed_at=processed_at,
            commit=not advances_checkpoint,
        )
        if finalized and advances_checkpoint and event.sequence is not None:
            self._advance_checkpoint(subscription.id, event.subject, event.sequence, processed_at)
            self.session.commit()
        return finalized

    def _check_order(
        self,
        event: InboundEvent,
        subscription: Subscription,
        delivery: Delivery,
        processed_at: datetime,
    ) -> bool | None:
        if event.sequence is None:
            return None
        checkpoint = self.session.scalar(
            select(ConsumerCheckpoint).where(
                ConsumerCheckpoint.subscription_id == subscription.id,
                ConsumerCheckpoint.subject == event.subject,
            )
        )
        last_sequence = checkpoint.last_sequence if checkpoint else 0
        if event.sequence <= last_sequence:
            return self._finalize_without_attempt(
                delivery,
                status=DeliveryStatus.SKIPPED,
                action="delivery_skipped",
                error_code="sequence_already_processed",
                error_message="Event sequence is not newer than the consumer checkpoint",
                processed_at=processed_at,
            )
        if event.sequence > last_sequence + 1:
            return self._finalize_without_attempt(
                delivery,
                status=DeliveryStatus.BLOCKED,
                action="delivery_blocked",
                error_code="sequence_gap",
                error_message="An earlier event sequence has not been delivered",
                processed_at=processed_at,
                available_at=processed_at + timedelta(seconds=self.settings.retry_base_seconds),
            )
        return None

    def _record_result(
        self,
        delivery: Delivery,
        *,
        worker_id: str,
        result: DeliveryResult,
        processed_at: datetime,
        commit: bool = True,
    ) -> bool:
        attempt = delivery.attempts + 1
        if result.succeeded:
            next_status = DeliveryStatus.DELIVERED
            available_at = delivery.available_at
            action = "delivery_completed"
            delivered_at = processed_at
        elif not result.transient or attempt >= self.settings.delivery_max_attempts:
            next_status = DeliveryStatus.DEAD
            available_at = delivery.available_at
            action = "delivery_dead_lettered"
            delivered_at = None
        else:
            next_status = DeliveryStatus.PENDING
            available_at = processed_at + retry_delay(
                attempt,
                delivery.idempotency_key,
                self.settings.retry_base_seconds,
                self.settings.retry_max_seconds,
            )
            action = "delivery_retry_scheduled"
            delivered_at = None
        finalized = self.session.execute(
            update(Delivery)
            .where(
                Delivery.id == delivery.id,
                Delivery.status == DeliveryStatus.DELIVERING,
                Delivery.worker_id == worker_id,
                Delivery.fencing_token == delivery.fencing_token,
                Delivery.lease_expires_at >= processed_at,
            )
            .values(
                status=next_status,
                attempts=attempt,
                available_at=available_at,
                worker_id=None,
                lease_expires_at=None,
                delivered_at=delivered_at,
                response_code=result.status_code,
                error_code=result.error_code,
                error_message=(
                    result.error_message[:1000] if result.error_message is not None else None
                ),
            )
            .execution_options(synchronize_session=False)
        )
        if finalized.rowcount != 1:
            self.session.rollback()
            return False
        append_audit(
            self.session,
            aggregate_type="delivery",
            aggregate_id=delivery.id,
            action=action,
            actor=worker_id,
            correlation_id=self._correlation_id(delivery.event_id),
            details={"attempt": attempt, "status": next_status.value},
        )
        if commit:
            self.session.commit()
        return True

    def _finalize_without_attempt(
        self,
        delivery: Delivery,
        *,
        status: DeliveryStatus,
        action: str,
        error_code: str,
        error_message: str,
        processed_at: datetime,
        available_at: datetime | None = None,
    ) -> bool:
        finalized = self.session.execute(
            update(Delivery)
            .where(
                Delivery.id == delivery.id,
                Delivery.status == DeliveryStatus.DELIVERING,
                Delivery.worker_id == delivery.worker_id,
                Delivery.fencing_token == delivery.fencing_token,
                Delivery.lease_expires_at >= processed_at,
            )
            .values(
                status=status,
                available_at=available_at or delivery.available_at,
                worker_id=None,
                lease_expires_at=None,
                error_code=error_code,
                error_message=error_message,
            )
            .execution_options(synchronize_session=False)
        )
        if finalized.rowcount != 1:
            self.session.rollback()
            return False
        append_audit(
            self.session,
            aggregate_type="delivery",
            aggregate_id=delivery.id,
            action=action,
            actor=delivery.worker_id or "unknown",
            correlation_id=self._correlation_id(delivery.event_id),
            details={"status": status.value},
        )
        self.session.commit()
        return True

    def _advance_checkpoint(
        self,
        subscription_id: str,
        subject: str,
        sequence: int,
        processed_at: datetime,
    ) -> None:
        checkpoint = self.session.scalar(
            select(ConsumerCheckpoint).where(
                ConsumerCheckpoint.subscription_id == subscription_id,
                ConsumerCheckpoint.subject == subject,
            )
        )
        if checkpoint is None:
            self.session.add(
                ConsumerCheckpoint(
                    subscription_id=subscription_id,
                    subject=subject,
                    last_sequence=sequence,
                    updated_at=processed_at,
                )
            )
            return
        if sequence > checkpoint.last_sequence:
            checkpoint.last_sequence = sequence
            checkpoint.updated_at = processed_at

    def _correlation_id(self, event_id: str) -> str:
        event = self.session.get(InboundEvent, event_id)
        return event.correlation_id if event is not None else event_id

    def _owns_lease(
        self,
        delivery: Delivery,
        worker_id: str,
        processed_at: datetime,
    ) -> bool:
        delivery_id = self.session.scalar(
            select(Delivery.id).where(
                Delivery.id == delivery.id,
                Delivery.status == DeliveryStatus.DELIVERING,
                Delivery.worker_id == worker_id,
                Delivery.fencing_token == delivery.fencing_token,
                Delivery.lease_expires_at >= processed_at,
            )
        )
        return delivery_id is not None


def retry_delay(
    attempt: int,
    idempotency_key: str,
    base_seconds: int,
    max_seconds: int,
) -> timedelta:
    exponential = base_seconds * (2 ** max(attempt - 1, 0))
    digest = hashlib.sha256(f"{idempotency_key}:{attempt}".encode()).digest()
    jitter = int.from_bytes(digest[:2]) % base_seconds
    return timedelta(seconds=min(exponential + jitter, max_seconds))
