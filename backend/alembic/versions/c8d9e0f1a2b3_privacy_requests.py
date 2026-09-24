"""add privacy lifecycle requests

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c8d9e0f1a2b3"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "privacy_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("subject_hash", sa.String(length=64), nullable=False),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("execute_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.CheckConstraint("request_type IN ('account_deletion')", name="ck_privacy_requests_type"),
        sa.CheckConstraint("status IN ('pending','cancelled','completed')", name="ck_privacy_requests_status"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_privacy_requests_user_id", "privacy_requests", ["user_id"])
    op.create_index("ix_privacy_requests_subject_hash", "privacy_requests", ["subject_hash"])
    op.create_index("ix_privacy_requests_execute_after", "privacy_requests", ["execute_after"])
    op.create_index("idx_privacy_requests_due", "privacy_requests", ["status", "execute_after"])
    op.create_index(
        "uq_privacy_requests_pending_subject_type",
        "privacy_requests",
        ["subject_hash", "request_type"],
        unique=True,
        sqlite_where=sa.text("status = 'pending'"),
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_table("privacy_requests")
