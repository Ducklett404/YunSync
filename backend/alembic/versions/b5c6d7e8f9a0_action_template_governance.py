"""action template governance and versioning

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-09-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, None] = "a4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_action_templates_code", table_name="action_templates")
    op.add_column(
        "action_templates",
        sa.Column("version", sa.String(length=32), server_default="1.0.0", nullable=False),
    )
    op.add_column(
        "action_templates",
        sa.Column(
            "review_status",
            sa.String(length=32),
            server_default="prototype_approved",
            nullable=False,
        ),
    )
    op.add_column(
        "action_templates",
        sa.Column(
            "review_scope",
            sa.String(length=32),
            server_default="prototype_rules",
            nullable=False,
        ),
    )
    op.add_column(
        "action_templates", sa.Column("reviewer_ref", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "action_templates", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "action_templates",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "action_templates", sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "action_templates",
        sa.Column(
            "contraindication_codes", sa.JSON(), server_default=sa.text("'[]'"), nullable=False
        ),
    )
    op.add_column(
        "action_templates",
        sa.Column("signal_metric_codes", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    )
    op.add_column(
        "action_templates",
        sa.Column(
            "ranking_policy_version",
            sa.String(length=32),
            server_default="rank-v1",
            nullable=False,
        ),
    )
    op.add_column(
        "action_templates",
        sa.Column(
            "explanation_policy_version",
            sa.String(length=32),
            server_default="action-explain-v1",
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE action_templates SET reviewer_ref = :reviewer "
            "WHERE review_status = 'prototype_approved'"
        ).bindparams(reviewer="synthetic-seed")
    )
    signal_codes = {
        "postmeal_walk": '["bmi","fasting_glucose","triglyceride"]',
        "drink_swap": '["bmi","fasting_glucose","triglyceride"]',
        "meal_order": '["fasting_glucose","triglyceride"]',
    }
    for code, codes in signal_codes.items():
        op.execute(
            sa.text(
                "UPDATE action_templates SET signal_metric_codes = :codes WHERE code = :code"
            ).bindparams(codes=codes, code=code)
        )
    op.create_index("ix_action_templates_code", "action_templates", ["code"], unique=False)
    op.create_index(
        "uq_action_templates_code_version",
        "action_templates",
        ["code", "version"],
        unique=True,
    )
    op.create_index(
        "uq_action_templates_active_code",
        "action_templates",
        ["code"],
        unique=True,
        sqlite_where=sa.text("is_active = 1"),
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_action_templates_active_code", table_name="action_templates")
    op.drop_index("uq_action_templates_code_version", table_name="action_templates")
    op.drop_index("ix_action_templates_code", table_name="action_templates")
    op.drop_column("action_templates", "explanation_policy_version")
    op.drop_column("action_templates", "ranking_policy_version")
    op.drop_column("action_templates", "signal_metric_codes")
    op.drop_column("action_templates", "contraindication_codes")
    op.drop_column("action_templates", "deactivated_at")
    op.drop_column("action_templates", "is_active")
    op.drop_column("action_templates", "reviewed_at")
    op.drop_column("action_templates", "reviewer_ref")
    op.drop_column("action_templates", "review_scope")
    op.drop_column("action_templates", "review_status")
    op.drop_column("action_templates", "version")
    op.create_index("ix_action_templates_code", "action_templates", ["code"], unique=True)
