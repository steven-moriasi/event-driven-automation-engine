from sqlalchemy.orm import Session

from app.domain.models import Subscription
from app.domain.schemas import SubscriptionCreate
from app.infrastructure.auth import Actor
from app.services.audit import append_audit


def create_subscription(
    session: Session,
    request: SubscriptionCreate,
    actor: Actor,
    correlation_id: str,
) -> Subscription:
    subscription = Subscription(
        name=request.name,
        event_type=request.event_type,
        adapter_type=request.adapter_type,
        endpoint_url=str(request.endpoint_url),
    )
    session.add(subscription)
    session.flush()
    append_audit(
        session,
        aggregate_type="subscription",
        aggregate_id=subscription.id,
        action="subscription_created",
        actor=actor.id,
        correlation_id=correlation_id,
        details={"adapter_type": subscription.adapter_type.value},
    )
    session.commit()
    return subscription
