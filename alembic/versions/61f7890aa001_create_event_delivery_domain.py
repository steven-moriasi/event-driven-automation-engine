"""Create event delivery domain.

Revision ID: 61f7890aa001
Revises:
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "61f7890aa001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False),
        sa.Column("adapter_type", sa.String(length=15), nullable=False),
        sa.Column("endpoint_url", sa.String(length=2048), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        op.f("ix_subscriptions_event_type"),
        "subscriptions",
        ["event_type"],
        unique=False,
    )
    op.create_table(
        "inbound_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="received", nullable=False),
        sa.Column("correlation_id", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "external_id",
            name="uq_event_source_external_id",
        ),
    )
    op.create_index(
        op.f("ix_inbound_events_correlation_id"),
        "inbound_events",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inbound_events_event_type"),
        "inbound_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_inbound_events_received",
        "inbound_events",
        ["received_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inbound_events_subject"),
        "inbound_events",
        ["subject"],
        unique=False,
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("aggregate_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("correlation_id", sa.String(length=255), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_aggregate",
        "audit_events",
        ["aggregate_type", "aggregate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_events_correlation_id"),
        "audit_events",
        ["correlation_id"],
        unique=False,
    )
    op.create_table(
        "deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("fencing_token", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["inbound_events.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id",
            "subscription_id",
            name="uq_delivery_event_subscription",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_delivery_idempotency_key"),
    )
    op.create_index(
        "ix_deliveries_claim",
        "deliveries",
        ["status", "available_at", "lease_expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_deliveries_event_id"),
        "deliveries",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_deliveries_subscription_id"),
        "deliveries",
        ["subscription_id"],
        unique=False,
    )
    op.create_table(
        "consumer_checkpoints",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("last_sequence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subscription_id",
            "subject",
            name="uq_checkpoint_subscription_subject",
        ),
    )
    op.create_index(
        op.f("ix_consumer_checkpoints_subscription_id"),
        "consumer_checkpoints",
        ["subscription_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_consumer_checkpoints_subscription_id"),
        table_name="consumer_checkpoints",
    )
    op.drop_table("consumer_checkpoints")
    op.drop_index(op.f("ix_deliveries_subscription_id"), table_name="deliveries")
    op.drop_index(op.f("ix_deliveries_event_id"), table_name="deliveries")
    op.drop_index("ix_deliveries_claim", table_name="deliveries")
    op.drop_table("deliveries")
    op.drop_index(op.f("ix_audit_events_correlation_id"), table_name="audit_events")
    op.drop_index("ix_audit_aggregate", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index(op.f("ix_inbound_events_subject"), table_name="inbound_events")
    op.drop_index("ix_inbound_events_received", table_name="inbound_events")
    op.drop_index(op.f("ix_inbound_events_event_type"), table_name="inbound_events")
    op.drop_index(op.f("ix_inbound_events_correlation_id"), table_name="inbound_events")
    op.drop_table("inbound_events")
    op.drop_index(op.f("ix_subscriptions_event_type"), table_name="subscriptions")
    op.drop_table("subscriptions")
