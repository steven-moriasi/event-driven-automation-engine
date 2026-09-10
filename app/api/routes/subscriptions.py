from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from app.domain.schemas import SubscriptionCreate, SubscriptionResponse
from app.infrastructure.auth import Actor, require_operator
from app.infrastructure.database import get_session
from app.services.catalog import create_subscription

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def post_subscription(
    request: SubscriptionCreate,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[Actor, Depends(require_operator)],
    correlation_id: Annotated[str | None, Header(alias="X-Correlation-ID")] = None,
) -> SubscriptionResponse:
    subscription = create_subscription(
        session,
        request,
        actor,
        correlation_id or str(uuid4()),
    )
    return SubscriptionResponse(
        id=subscription.id,
        name=subscription.name,
        event_type=subscription.event_type,
        adapter_type=subscription.adapter_type,
        endpoint_url=subscription.endpoint_url,
        enabled=subscription.enabled,
    )
