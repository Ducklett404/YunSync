"""Add V2 care plan feedback, reminders, and revision history.

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "a6b7c8d9e0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("care_plans") as batch:
        batch.add_column(sa.Column("pause_reason", sa.String(length=40)))
        batch.add_column(sa.Column("superseded_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("previous_plan_id", sa.String(length=36)))
        batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch.create_foreign_key("fk_care_plans_previous", "care_plans", ["previous_plan_id"], ["id"], ondelete="SET NULL")
        batch.drop_constraint("ck_care_plans_status", type_="check")
        batch.create_check_constraint(
            "ck_care_plans_status", "status IN ('READY', 'ACTIVE', 'PAUSED', 'SUPERSEDED')"
        )
    # Existing M5 users may already have several immutable snapshots. Preserve
    # their chronological version numbers when running against a live database.
    if not op.get_context().as_sql:
        connection = op.get_bind()
        rows = list(connection.execute(sa.text(
            "SELECT id, user_id FROM care_plans ORDER BY user_id, created_at, id"
        )))
        current_user = None
        version = 0
        for plan_id, user_id in rows:
            version = version + 1 if user_id == current_user else 1
            current_user = user_id
            connection.execute(sa.text(
                "UPDATE care_plans SET version = :version WHERE id = :plan_id"
            ), {"version": version, "plan_id": plan_id})
    op.create_index(
        "uq_care_plans_user_version", "care_plans", ["user_id", "version"], unique=True
    )

    op.create_table(
        "adherence_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.String(length=36), sa.ForeignKey("care_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("replacement", sa.String(length=120), nullable=False),
        sa.Column("discomfort", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("day BETWEEN 1 AND 7", name="ck_adherence_logs_day"),
        sa.CheckConstraint("status IN ('completed', 'skipped', 'replaced')", name="ck_adherence_logs_status"),
    )
    op.create_index("uq_adherence_logs_plan_day", "adherence_logs", ["plan_id", "day"], unique=True)

    op.create_table(
        "follow_up_reminders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.String(length=36), sa.ForeignKey("care_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("remind_on", sa.Date(), nullable=False),
        sa.Column("basis", sa.String(length=16), nullable=False),
        sa.Column("note", sa.String(length=240), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("uq_follow_up_reminders_plan", "follow_up_reminders", ["plan_id"], unique=True)

    op.create_table(
        "plan_revisions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("old_plan_id", sa.String(length=36), sa.ForeignKey("care_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("new_plan_id", sa.String(length=36), sa.ForeignKey("care_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("new_report_id", sa.String(length=36), sa.ForeignKey("health_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("comparison", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("uq_plan_revisions_new_plan", "plan_revisions", ["new_plan_id"], unique=True)
    op.create_index("uq_plan_revisions_old_plan", "plan_revisions", ["old_plan_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_plan_revisions_old_plan", table_name="plan_revisions")
    op.drop_index("uq_plan_revisions_new_plan", table_name="plan_revisions")
    op.drop_table("plan_revisions")
    op.drop_index("uq_follow_up_reminders_plan", table_name="follow_up_reminders")
    op.drop_table("follow_up_reminders")
    op.drop_index("uq_adherence_logs_plan_day", table_name="adherence_logs")
    op.drop_table("adherence_logs")
    op.drop_index("uq_care_plans_user_version", table_name="care_plans")
    # M5 knows no SUPERSEDED state; preserve the old snapshot as PAUSED.
    op.execute("UPDATE care_plans SET status = 'PAUSED' WHERE status = 'SUPERSEDED'")
    with op.batch_alter_table("care_plans") as batch:
        batch.drop_constraint("ck_care_plans_status", type_="check")
        batch.create_check_constraint("ck_care_plans_status", "status IN ('READY', 'ACTIVE', 'PAUSED')")
        batch.drop_constraint("fk_care_plans_previous", type_="foreignkey")
        batch.drop_column("version")
        batch.drop_column("previous_plan_id")
        batch.drop_column("superseded_at")
        batch.drop_column("pause_reason")
