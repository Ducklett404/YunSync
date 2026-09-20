"""Add structured food safety profile for V2.

Revision ID: b1c2d3e4f5a6
Revises: 0a1b2c3d4e5f
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "0a1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_safety_profiles",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("allergy_status", sa.String(length=16), nullable=False),
        sa.Column("allergens", sa.JSON(), nullable=False),
        sa.Column("medication_status", sa.String(length=16), nullable=False),
        sa.Column("medications", sa.JSON(), nullable=False),
        sa.Column("condition_status", sa.String(length=16), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("clinician_restriction_status", sa.String(length=16), nullable=False),
        sa.Column("clinician_restrictions", sa.JSON(), nullable=False),
        sa.Column("special_status", sa.String(length=24), nullable=False),
        sa.Column("special_details", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("food_safety_profiles")
