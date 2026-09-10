from pydantic import JsonValue
from sqlalchemy.orm import Session

from app.domain.models import AuditEvent


def append_audit(
    session: Session,
    *,
    aggregate_type: str,
    aggregate_id: str,
    action: str,
    actor: str,
    correlation_id: str,
    details: dict[str, JsonValue] | None = None,
) -> None:
    session.add(
        AuditEvent(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            action=action,
            actor=actor,
            correlation_id=correlation_id,
            details=details or {},
        )
    )
