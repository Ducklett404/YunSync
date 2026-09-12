"""add indexes for common dashboard queries

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-09-12
"""

from collections.abc import Sequence

from alembic import op


revision: str = "f9a0b1c2d3e4"
down_revision: str | None = "e8f9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_experiments_user_created",
        "experiments",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_health_metrics_report_name",
        "health_metrics",
        ["report_id", "name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_health_metrics_report_name", table_name="health_metrics")
    op.drop_index("idx_experiments_user_created", table_name="experiments")
