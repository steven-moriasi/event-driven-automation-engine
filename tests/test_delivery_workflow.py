from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.domain.enums import AdapterType, DeliveryStatus, EventStatus
from app.domain.models import (
    AuditEvent,
    ConsumerCheckpoint,
    Delivery,
    InboundEvent,
    Subscription,
)
from app.services.adapters import DeliveryResult
from app.services.deliveries import DeliveryProcessor, claim_next_delivery
from app.services.recovery import recover_expired_deliveries


class RecordingAdapter:
    def __init__(self, results: Sequence[DeliveryResult]) -> None:
        self.results = list(results)
        self.calls = 0

    def deliver(
        self,
        event: InboundEvent,
        subscription: Subscription,
        idempotency_key: str,
    ) -> DeliveryResult:
        del event, subscription, idempotency_key
        self.calls += 1
        return self.results.pop(0)


def successful_result() -> DeliveryResult:
    return DeliveryResult(
        succeeded=True,
        transient=False,
        status_code=202,
        error_code=None,
        error_message=None,
    )


def transient_result() -> DeliveryResult:
    return DeliveryResult(
        succeeded=False,
        transient=True,
        status_code=503,
        error_code="upstream_unavailable",
        error_message="Upstream service is temporarily unavailable",
    )


def add_subscription(session: Session) -> Subscription:
    subscription = Subscription(
        name="Workflow consumer",
        event_type="order.created",
        adapter_type=AdapterType.GENERIC_WEBHOOK,
        endpoint_url="https://consumer.example/events",
    )
    session.add(subscription)
    session.flush()
    return subscription


def add_delivery(
    session: Session,
    subscription: Subscription,
    *,
    external_id: str,
    sequence: int | None,
    available_at: datetime,
) -> Delivery:
    event = InboundEvent(
        source="partner",
        external_id=external_id,
        event_type="order.created",
        subject="order-42",
        sequence=sequence,
        occurred_at=available_at,
        received_at=available_at,
        payload={
            "id": external_id,
            "type": "order.created",
            "subject": "order-42",
            "occurred_at": available_at.isoformat(),
            "sequence": sequence,
            "data": {"reference": external_id},
            "metadata": {},
        },
        payload_hash=external_id.rjust(64, "0")[-64:],
        status=EventStatus.DISPATCHED,
        correlation_id=f"correlation-{external_id}",
    )
    session.add(event)
    session.flush()
    delivery = Delivery(
        event_id=event.id,
        subscription_id=subscription.id,
        idempotency_key=f"partner:{external_id}:{subscription.id}",
        available_at=available_at,
    )
    session.add(delivery)
    session.commit()
    return delivery


def test_delivery_advances_checkpoint_and_handles_sequence_order(
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    started_at = datetime(2025, 1, 1, tzinfo=UTC)
    adapter = RecordingAdapter([successful_result(), successful_result()])
    with session_factory() as session:
        subscription = add_subscription(session)
        second = add_delivery(
            session,
            subscription,
            external_id="event-2",
            sequence=2,
            available_at=started_at,
        )

        claimed_second = claim_next_delivery(
            session,
            worker_id="worker-1",
            lease_seconds=60,
            now=started_at,
        )
        assert claimed_second is not None
        assert DeliveryProcessor(session, settings).process(
            claimed_second,
            worker_id="worker-1",
            adapter=adapter,
            now=started_at,
        )
        session.refresh(second)
        assert second.status == DeliveryStatus.BLOCKED
        assert second.attempts == 0
        assert adapter.calls == 0

        first = add_delivery(
            session,
            subscription,
            external_id="event-1",
            sequence=1,
            available_at=started_at,
        )
        claimed_first = claim_next_delivery(
            session,
            worker_id="worker-1",
            lease_seconds=60,
            now=started_at,
        )
        assert claimed_first is not None
        assert claimed_first.id == first.id
        assert DeliveryProcessor(session, settings).process(
            claimed_first,
            worker_id="worker-1",
            adapter=adapter,
            now=started_at,
        )

        second.available_at = started_at
        session.commit()
        claimed_second = claim_next_delivery(
            session,
            worker_id="worker-2",
            lease_seconds=60,
            now=started_at,
        )
        assert claimed_second is not None
        assert claimed_second.id == second.id
        assert DeliveryProcessor(session, settings).process(
            claimed_second,
            worker_id="worker-2",
            adapter=adapter,
            now=started_at,
        )

        checkpoint = session.scalar(select(ConsumerCheckpoint))
        completed_second = session.get(Delivery, second.id, populate_existing=True)
        assert checkpoint is not None
        assert completed_second is not None
        assert checkpoint.last_sequence == 2
        assert completed_second.status == DeliveryStatus.DELIVERED
        assert adapter.calls == 2

        repeated = add_delivery(
            session,
            subscription,
            external_id="event-1-repeated",
            sequence=1,
            available_at=started_at,
        )
        claimed_repeated = claim_next_delivery(
            session,
            worker_id="worker-3",
            lease_seconds=60,
            now=started_at,
        )
        assert claimed_repeated is not None
        assert DeliveryProcessor(session, settings).process(
            claimed_repeated,
            worker_id="worker-3",
            adapter=adapter,
            now=started_at,
        )
        session.refresh(repeated)
        assert repeated.status == DeliveryStatus.SKIPPED
        assert repeated.error_code == "sequence_already_processed"
        assert adapter.calls == 2


def test_transient_delivery_retries_then_dead_letters_and_replays(
    client: TestClient,
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    started_at = datetime(2025, 1, 1, tzinfo=UTC)
    adapter = RecordingAdapter([transient_result(), transient_result()])
    with session_factory() as session:
        subscription = add_subscription(session)
        delivery = add_delivery(
            session,
            subscription,
            external_id="retry-event",
            sequence=None,
            available_at=started_at,
        )
        for worker_id, attempted_at in (
            ("worker-1", started_at),
            ("worker-2", started_at + timedelta(seconds=2)),
        ):
            delivery.available_at = attempted_at
            session.commit()
            claimed = claim_next_delivery(
                session,
                worker_id=worker_id,
                lease_seconds=60,
                now=attempted_at,
            )
            assert claimed is not None
            assert DeliveryProcessor(session, settings).process(
                claimed,
                worker_id=worker_id,
                adapter=adapter,
                now=attempted_at,
            )
        session.refresh(delivery)
        assert delivery.status == DeliveryStatus.DEAD
        assert delivery.attempts == 2
        assert delivery.error_message == "Upstream service is temporarily unavailable"
        delivery_id = delivery.id

    forbidden = client.post(
        f"/deliveries/{delivery_id}/replay",
        headers={"X-Actor-ID": "viewer-1", "X-Actor-Roles": "viewer"},
        json={"reason": "Investigate provider recovery"},
    )
    assert forbidden.status_code == 403

    replayed = client.post(
        f"/deliveries/{delivery_id}/replay",
        headers={
            "X-Actor-ID": "operator-1",
            "X-Actor-Roles": "operator",
            "X-Correlation-ID": "replay-correlation",
        },
        json={"reason": "Provider recovered after maintenance"},
    )
    assert replayed.status_code == 200
    assert replayed.json()["status"] == "pending"
    assert replayed.json()["attempts"] == 0
    assert replayed.json()["replay_count"] == 1

    with session_factory() as session:
        audit = session.scalar(
            select(AuditEvent).where(AuditEvent.action == "delivery_replayed")
        )
        assert audit is not None
        assert audit.actor == "operator-1"
        assert audit.details["reason"] == "Provider recovered after maintenance"


def test_recovery_reclaims_expired_lease_and_fences_stale_worker(
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    started_at = datetime(2025, 1, 1, tzinfo=UTC)
    with session_factory() as setup_session:
        subscription = add_subscription(setup_session)
        delivery = add_delivery(
            setup_session,
            subscription,
            external_id="leased-event",
            sequence=None,
            available_at=started_at,
        )
        delivery_id = delivery.id

    stale_session = session_factory()
    active_session = session_factory()
    try:
        stale_claim = claim_next_delivery(
            stale_session,
            worker_id="stale-worker",
            lease_seconds=60,
            now=started_at,
        )
        assert stale_claim is not None
        recovered_at = started_at + timedelta(seconds=61)
        assert (
            recover_expired_deliveries(
                active_session,
                actor="lease-reaper",
                now=recovered_at,
            )
            == 1
        )
        active_claim = claim_next_delivery(
            active_session,
            worker_id="active-worker",
            lease_seconds=60,
            now=recovered_at,
        )
        assert active_claim is not None
        assert active_claim.fencing_token == stale_claim.fencing_token + 1

        stale_adapter = RecordingAdapter([successful_result()])
        assert not DeliveryProcessor(stale_session, settings).process(
            stale_claim,
            worker_id="stale-worker",
            adapter=stale_adapter,
            now=recovered_at,
        )
        assert stale_adapter.calls == 0

        active_adapter = RecordingAdapter([successful_result()])
        assert DeliveryProcessor(active_session, settings).process(
            active_claim,
            worker_id="active-worker",
            adapter=active_adapter,
            now=recovered_at,
        )
        active_session.expire_all()
        completed = active_session.get(Delivery, delivery_id)
        assert completed is not None
        assert completed.status == DeliveryStatus.DELIVERED
    finally:
        stale_session.close()
        active_session.close()
