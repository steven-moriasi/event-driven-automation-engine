import time

import structlog
from prometheus_client import start_http_server

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import DELIVERIES_RECOVERED
from app.infrastructure.database import SessionLocal
from app.services.recovery import recover_expired_deliveries


def run() -> None:
    configure_logging()
    logger = structlog.get_logger()
    settings = get_settings()
    start_http_server(settings.process_metrics_port)
    while True:
        with SessionLocal() as session:
            count = recover_expired_deliveries(
                session,
                actor="delivery-reaper",
            )
        if count:
            DELIVERIES_RECOVERED.inc(count)
            logger.warning("delivery_leases_recovered", count=count)
        time.sleep(settings.recovery_interval_seconds)


if __name__ == "__main__":
    run()
