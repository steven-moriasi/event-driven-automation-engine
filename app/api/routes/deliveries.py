from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.domain.models import Delivery
from app.domain.schemas import DeliveryResponse, ReplayRequest
from app.infrastructure.auth import Actor, require_operator
from app.infrastructure.database import get_session
from app.services.recovery import replay_dead_delivery

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


def delivery_response(delivery: Delivery) -> DeliveryResponse:
    return DeliveryResponse(
        id=delivery.id,
        event_id=delivery.event_id,
        subscription_id=delivery.subscription_id,
        status=delivery.status,
        attempts=delivery.attempts,
        replay_count=delivery.replay_count,
        available_at=delivery.available_at,
        delivered_at=delivery.delivered_at,
        error_code=delivery.error_code,
    )


@router.get("/{delivery_id}", response_model=DeliveryResponse)
def get_delivery(
    delivery_id: str,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[Actor, Depends(require_operator)],
) -> DeliveryResponse:
    del actor
    delivery = session.get(Delivery, delivery_id)
    if delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")
    return delivery_response(delivery)


@router.post("/{delivery_id}/replay", response_model=DeliveryResponse)
def replay_delivery(
    delivery_id: str,
    request: ReplayRequest,
    session: Annotated[Session, Depends(get_session)],
    actor: Annotated[Actor, Depends(require_operator)],
    correlation_id: Annotated[str | None, Header(alias="X-Correlation-ID")] = None,
) -> DeliveryResponse:
    delivery = session.get(Delivery, delivery_id)
    if delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")
    replayed = replay_dead_delivery(
        session,
        delivery=delivery,
        actor=actor,
        reason=request.reason,
        correlation_id=correlation_id or str(uuid4()),
    )
    if replayed is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an unchanged dead-letter delivery can be replayed",
        )
    return delivery_response(replayed)
