"""Add reported display precision for conservative comparisons.

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d9e0f1a2b3c4"
down_revision: str | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "health_metrics",
        sa.Column("reported_precision", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("health_metrics", "reported_precision")
