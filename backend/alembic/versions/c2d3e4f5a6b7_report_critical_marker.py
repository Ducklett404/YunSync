"""Add user-confirmed report critical marker.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "health_reports",
        sa.Column("critical_marker_status", sa.String(length=16), server_default="unknown", nullable=False),
    )
    op.add_column(
        "health_reports",
        sa.Column("critical_marker_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("health_reports", "critical_marker_reviewed_at")
    op.drop_column("health_reports", "critical_marker_status")
