import time
from uuid import uuid4

import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.domain.models import Subscription
from app.infrastructure.database import SessionLocal
from app.infrastructure.http_adapters import AdapterRegistry
from app.services.deliveries import DeliveryProcessor, claim_next_delivery


def run() -> None:
    configure_logging()
    logger = structlog.get_logger()
    settings = get_settings()
    worker_id = f"delivery-worker:{uuid4()}"
    registry = AdapterRegistry(settings)
    logger.info("worker_started", worker_id=worker_id)
    while True:
        with SessionLocal() as session:
            delivery = claim_next_delivery(
                session,
                worker_id=worker_id,
                lease_seconds=settings.delivery_lease_seconds,
            )
            if delivery is None:
                time.sleep(settings.worker_poll_seconds)
                continue
            subscription = session.get(Subscription, delivery.subscription_id)
            if subscription is None:
                logger.error("subscription_missing", delivery_id=delivery.id)
                continue
            processed = DeliveryProcessor(session, settings).process(
                delivery,
                worker_id=worker_id,
                adapter=registry.for_type(subscription.adapter_type),
            )
            logger.info(
                "delivery_processed",
                delivery_id=delivery.id,
                finalized=processed,
            )


if __name__ == "__main__":
    run()
