"""experiment state machine and locked schedule

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-09-11
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEDULE_VERSION = "balanced-14-v1"


def _schedule_digest(row) -> str:
    schedule = row["schedule"]
    if isinstance(schedule, str):
        schedule = json.loads(schedule)
    payload = {
        "version": SCHEDULE_VERSION,
        "start_date": row["start_date"].isoformat(),
        "end_date": row["end_date"].isoformat(),
        "seed": row["randomization_seed"],
        "schedule": schedule,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def upgrade() -> None:
    op.add_column(
        "experiments",
        sa.Column(
            "schedule_version",
            sa.String(length=32),
            server_default=SCHEDULE_VERSION,
            nullable=False,
        ),
    )
    op.add_column(
        "experiments",
        sa.Column(
            "schedule_hash",
            sa.String(length=64),
            server_default="",
            nullable=False,
        ),
    )
    op.add_column(
        "experiments", sa.Column("schedule_locked_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "experiments", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "experiments", sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "experiments", sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "experiments", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "experiments", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
    )

    experiments = sa.table(
        "experiments",
        sa.column("id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("status", sa.String),
        sa.column("start_date", sa.Date),
        sa.column("end_date", sa.Date),
        sa.column("randomization_seed", sa.Integer),
        sa.column("schedule", sa.JSON),
        sa.column("schedule_hash", sa.String),
        sa.column("schedule_locked_at", sa.DateTime(timezone=True)),
        sa.column("started_at", sa.DateTime(timezone=True)),
        sa.column("paused_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    offline = context.is_offline_mode()
    bind = None if offline else op.get_bind()
    if bind is not None:
        rows = list(bind.execute(sa.select(experiments)).mappings())
        now = datetime.now(timezone.utc)
        active_seen: set[str] = set()
        rows.sort(key=lambda row: (row["user_id"], row["created_at"] or now), reverse=True)
        for row in rows:
            values = {
                "schedule_hash": _schedule_digest(row),
                "schedule_locked_at": row["created_at"] or now,
                "started_at": row["created_at"] or now,
                "updated_at": row["created_at"] or now,
            }
            if row["status"] == "active":
                if row["user_id"] in active_seen:
                    values.update(status="paused", paused_at=now, updated_at=now)
                else:
                    active_seen.add(row["user_id"])
            bind.execute(
                sa.update(experiments)
                .where(experiments.c.id == row["id"])
                .values(**values)
            )

    with op.batch_alter_table("experiments") as batch_op:
        batch_op.alter_column("schedule_locked_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch_op.alter_column("started_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch_op.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch_op.create_check_constraint(
            "ck_experiments_status",
            "status IN ('active','paused','terminated','completed')",
        )

    op.create_index(
        "uq_experiments_active_user",
        "experiments",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )
    if bind is not None and bind.dialect.name == "sqlite":
        bind.exec_driver_sql("PRAGMA optimize")


def downgrade() -> None:
    op.drop_index("uq_experiments_active_user", table_name="experiments")
    with op.batch_alter_table("experiments") as batch_op:
        batch_op.drop_constraint("ck_experiments_status", type_="check")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("terminated_at")
        batch_op.drop_column("paused_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("schedule_locked_at")
        batch_op.drop_column("schedule_hash")
        batch_op.drop_column("schedule_version")
