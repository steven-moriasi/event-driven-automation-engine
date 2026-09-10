"""Add delivery replay tracking.

Revision ID: 92b7e11cd002
Revises: 61f7890aa001
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "92b7e11cd002"
down_revision: str | None = "61f7890aa001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "deliveries",
        sa.Column("replay_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "deliveries",
        sa.Column("last_replayed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("deliveries", "last_replayed_at")
    op.drop_column("deliveries", "replay_count")
