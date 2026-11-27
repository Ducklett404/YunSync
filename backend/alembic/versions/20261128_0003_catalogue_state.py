"""Track the catalogue revision used by recipe and recommendation caches."""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op


revision = "20261128_0003"
down_revision = "20261009_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    state = op.create_table(
        "catalogue_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision", sa.String(32), nullable=False),
    )
    op.bulk_insert(state, [{"id": 1, "revision": uuid4().hex}])


def downgrade() -> None:
    op.drop_table("catalogue_state")
