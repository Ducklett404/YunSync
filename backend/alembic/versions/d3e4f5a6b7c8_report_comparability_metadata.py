"""Add report and metric comparability metadata.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "health_reports",
        sa.Column("institution", sa.String(length=120), server_default="", nullable=False),
    )
    op.add_column(
        "health_reports",
        sa.Column("examined_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "health_metrics",
        sa.Column("method", sa.String(length=120), server_default="", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("health_metrics", "method")
    op.drop_column("health_reports", "examined_at")
    op.drop_column("health_reports", "institution")
