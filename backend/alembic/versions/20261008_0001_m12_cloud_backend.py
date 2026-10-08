"""Create M12 recipe, seasonal content, and audit tables."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20261008_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recipes",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("servings", sa.Integer(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("ingredients", sa.JSON(), nullable=False),
        sa.Column("tools", sa.JSON(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("substitutions", sa.JSON(), nullable=False),
        sa.Column("allergens", sa.JSON(), nullable=False),
        sa.Column("exclusions", sa.JSON(), nullable=False),
        sa.Column("regions", sa.JSON(), nullable=False),
        sa.Column("scene_tags", sa.JSON(), nullable=False),
        sa.Column("source_note", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=180), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("version", sa.String(length=60), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("content_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recipes_category", "recipes", ["category"])
    op.create_index("ix_recipes_is_demo", "recipes", ["is_demo"])
    op.create_index("ix_recipes_review_status", "recipes", ["review_status"])
    op.create_index("ix_recipes_version", "recipes", ["version"])

    op.create_table(
        "seasonal_contents",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("culture_note", sa.Text(), nullable=False),
        sa.Column("date_rule", sa.JSON(), nullable=False),
        sa.Column("regions", sa.JSON(), nullable=False),
        sa.Column("recipe_ids", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=180), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("version", sa.String(length=60), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("content_updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_seasonal_contents_kind", "seasonal_contents", ["kind"])
    op.create_index("ix_seasonal_contents_is_demo", "seasonal_contents", ["is_demo"])
    op.create_index(
        "ix_seasonal_contents_review_status", "seasonal_contents", ["review_status"]
    )

    op.create_table(
        "recommendation_audits",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("request_kind", sa.String(length=20), nullable=False),
        sa.Column("rule_version", sa.String(length=40), nullable=False),
        sa.Column("candidate_ids", sa.JSON(), nullable=False),
        sa.Column("selected_ids", sa.JSON(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("degraded_flags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_recommendation_audits_request_kind",
        "recommendation_audits",
        ["request_kind"],
    )
    op.create_index(
        "ix_recommendation_audits_created_at",
        "recommendation_audits",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("recommendation_audits")
    op.drop_table("seasonal_contents")
    op.drop_table("recipes")
