"""Record minimal M13 model output metadata without storing user text."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20261009_0002"
down_revision: str | None = "20261008_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_output_audits",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("recipe_id", sa.String(length=80), nullable=True),
        sa.Column("recipe_version", sa.String(length=60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_output_audits_request_id", "ai_output_audits", ["request_id"])


def downgrade() -> None:
    op.drop_table("ai_output_audits")
