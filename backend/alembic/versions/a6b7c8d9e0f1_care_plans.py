"""Persist versioned V2 care plan snapshots.

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a6b7c8d9e0f1"
down_revision: str | None = "f5a6b7c8d9e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "care_plans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_id", sa.String(length=36), sa.ForeignKey("health_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("paused_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('READY', 'ACTIVE', 'PAUSED')", name="ck_care_plans_status"),
    )
    op.create_index("idx_care_plans_user_created", "care_plans", ["user_id", "created_at"])
    op.create_index("uq_care_plans_user_request", "care_plans", ["user_id", "request_hash"], unique=True)
    op.create_index(
        "uq_care_plans_user_active", "care_plans", ["user_id"], unique=True,
        sqlite_where=sa.text("status = 'ACTIVE'"),
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_care_plans_user_active", table_name="care_plans")
    op.drop_index("uq_care_plans_user_request", table_name="care_plans")
    op.drop_index("idx_care_plans_user_created", table_name="care_plans")
    op.drop_table("care_plans")
