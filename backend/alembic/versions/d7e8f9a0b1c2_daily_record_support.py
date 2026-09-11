"""daily record context, reminders and import support

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-09-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("reminder_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "user_profiles",
        sa.Column("reminder_time", sa.String(length=5), server_default="20:00", nullable=False),
    )
    op.add_column(
        "observations",
        sa.Column("discomfort_level", sa.String(length=16), server_default="none", nullable=False),
    )
    op.add_column(
        "observations", sa.Column("discomfort_details", sa.Text(), nullable=True)
    )
    op.add_column(
        "observations", sa.Column("unplanned_event", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("observations", "unplanned_event")
    op.drop_column("observations", "discomfort_details")
    op.drop_column("observations", "discomfort_level")
    op.drop_column("user_profiles", "reminder_time")
    op.drop_column("user_profiles", "reminder_enabled")
