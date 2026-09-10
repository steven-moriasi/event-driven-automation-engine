from enum import StrEnum


class EventStatus(StrEnum):
    RECEIVED = "received"
    DISPATCHED = "dispatched"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    DELIVERING = "delivering"
    BLOCKED = "blocked"
    DELIVERED = "delivered"
    SKIPPED = "skipped"
    DEAD = "dead"


class AdapterType(StrEnum):
    GENERIC_WEBHOOK = "generic_webhook"
    GITHUB_ISSUES = "github_issues"
    SLACK_WEBHOOK = "slack_webhook"
