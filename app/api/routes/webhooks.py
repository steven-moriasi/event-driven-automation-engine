import json
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.domain.schemas import EventEnvelope, EventResponse
from app.infrastructure.database import get_session
from app.infrastructure.signing import verify_signature
from app.services.ingestion import IdempotencyConflictError, ingest_event

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/{source}", response_model=EventResponse, status_code=status.HTTP_202_ACCEPTED)
async def post_webhook(
    source: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    signature: Annotated[str | None, Header(alias="X-Event-Signature")] = None,
    correlation_id: Annotated[str | None, Header(alias="X-Correlation-ID")] = None,
) -> EventResponse:
    payload = await request.body()
    if len(payload) > settings.max_event_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Event payload exceeds configured limit",
        )
    secret = settings.webhook_secrets.get(source)
    if secret is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown event source",
        )
    if signature is None or not verify_signature(payload, signature, secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid event signature",
        )
    try:
        envelope = EventEnvelope.model_validate(json.loads(payload))
    except (json.JSONDecodeError, ValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid event envelope",
        ) from error
    try:
        return ingest_event(
            session,
            source=source,
            envelope=envelope,
            correlation_id=correlation_id or str(uuid4()),
        )
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
