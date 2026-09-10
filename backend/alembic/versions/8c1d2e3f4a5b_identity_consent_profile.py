"""identity, consent and profile baseline

Revision ID: 8c1d2e3f4a5b
Revises: 6169c3448442
Create Date: 2026-09-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c1d2e3f4a5b"
down_revision: Union[str, None] = "6169c3448442"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("role", sa.String(length=20), server_default="participant", nullable=False),
    )
    op.add_column(
        "user_profiles",
        sa.Column("sleep_schedule", sa.String(length=120), server_default="", nullable=False),
    )
    op.add_column(
        "user_profiles",
        sa.Column("activity_baseline", sa.String(length=160), server_default="", nullable=False),
    )
    op.add_column(
        "user_profiles",
        sa.Column("constraints", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "user_profiles",
        sa.Column("preferences", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "user_profiles",
        sa.Column("screening_status", sa.String(length=32), server_default="pending", nullable=False),
    )
    op.add_column(
        "user_profiles",
        sa.Column("screening_answers", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )
    op.add_column(
        "user_profiles",
        sa.Column("screened_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False)
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True)
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"], unique=False)

    op.create_table(
        "consent_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'withdrawn')", name="ck_consent_status"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consent_records_user_id", "consent_records", ["user_id"], unique=False)
    op.create_index(
        "uq_consent_active_user",
        "consent_records",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_consent_active_user", table_name="consent_records")
    op.drop_index("ix_consent_records_user_id", table_name="consent_records")
    op.drop_table("consent_records")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")

    op.drop_column("user_profiles", "screened_at")
    op.drop_column("user_profiles", "screening_answers")
    op.drop_column("user_profiles", "screening_status")
    op.drop_column("user_profiles", "preferences")
    op.drop_column("user_profiles", "constraints")
    op.drop_column("user_profiles", "activity_baseline")
    op.drop_column("user_profiles", "sleep_schedule")
    op.drop_column("user_profiles", "role")
