"""prevent duplicate metric codes within one report

Revision ID: 0a1b2c3d4e5f
Revises: f9a0b1c2d3e4
Create Date: 2026-09-14
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0a1b2c3d4e5f"
down_revision: str | None = "f9a0b1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_health_metrics_report_code",
        "health_metrics",
        ["report_id", "code"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_health_metrics_report_code",
        table_name="health_metrics",
    )
