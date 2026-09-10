from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, JsonValue

from app.domain.enums import AdapterType, DeliveryStatus, EventStatus


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=255)
    type: str = Field(min_length=1, max_length=160)
    subject: str = Field(min_length=1, max_length=255)
    occurred_at: datetime
    sequence: int | None = Field(default=None, ge=1)
    data: dict[str, JsonValue]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class SubscriptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    event_type: str = Field(min_length=1, max_length=160)
    adapter_type: AdapterType
    endpoint_url: HttpUrl


class SubscriptionResponse(BaseModel):
    id: str
    name: str
    event_type: str
    adapter_type: AdapterType
    endpoint_url: str
    enabled: bool


class EventResponse(BaseModel):
    id: str
    external_id: str
    source: str
    event_type: str
    subject: str
    sequence: int | None
    status: EventStatus
    duplicate: bool
    delivery_count: int
    correlation_id: str


class DeliveryResponse(BaseModel):
    id: str
    event_id: str
    subscription_id: str
    status: DeliveryStatus
    attempts: int
    available_at: datetime
    delivered_at: datetime | None
    error_code: str | None


class ReplayRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
