"""Add professionally attested safety rule releases.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e4f5a6b7c8d9"
down_revision: str | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "food_safety_profiles",
        sa.Column("liver_kidney_status", sa.String(length=16), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "food_safety_profiles",
        sa.Column("liver_kidney_conditions", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.create_table(
        "safety_rule_releases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("evidence_ref", sa.String(length=240), nullable=False),
        sa.Column("reviewer_qualification", sa.String(length=160), nullable=False),
        sa.Column("reviewed_rule_codes", sa.JSON(), nullable=False),
        sa.Column("attested", sa.Boolean(), nullable=False),
        sa.Column("reviewer_id", sa.String(length=36), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_safety_rule_releases_version",
        "safety_rule_releases",
        ["version"],
        unique=True,
    )
    op.create_index(
        "uq_safety_rule_releases_published",
        "safety_rule_releases",
        ["status"],
        unique=True,
        sqlite_where=sa.text("status = 'published'"),
        postgresql_where=sa.text("status = 'published'"),
    )


def downgrade() -> None:
    op.drop_index("uq_safety_rule_releases_published", table_name="safety_rule_releases")
    op.drop_index("uq_safety_rule_releases_version", table_name="safety_rule_releases")
    op.drop_table("safety_rule_releases")
    op.drop_column("food_safety_profiles", "liver_kidney_conditions")
    op.drop_column("food_safety_profiles", "liver_kidney_status")
