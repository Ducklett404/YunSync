from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CarePlan(Base):
    __tablename__ = "care_plans"
    __table_args__ = (
        CheckConstraint("status IN ('READY', 'ACTIVE', 'PAUSED', 'SUPERSEDED')", name="ck_care_plans_status"),
        Index("idx_care_plans_user_created", "user_id", "created_at"),
        Index("uq_care_plans_user_request", "user_id", "request_hash", unique=True),
        Index("uq_care_plans_user_version", "user_id", "version", unique=True),
        Index(
            "uq_care_plans_user_active",
            "user_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"))
    report_id: Mapped[str] = mapped_column(ForeignKey("health_reports.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="READY")
    request_hash: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pause_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    previous_plan_id: Mapped[str | None] = mapped_column(ForeignKey("care_plans.id", ondelete="SET NULL"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class AdherenceLog(Base):
    __tablename__ = "adherence_logs"
    __table_args__ = (
        CheckConstraint("day BETWEEN 1 AND 7", name="ck_adherence_logs_day"),
        CheckConstraint("status IN ('completed', 'skipped', 'replaced')", name="ck_adherence_logs_status"),
        Index("uq_adherence_logs_plan_day", "plan_id", "day", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"))
    plan_id: Mapped[str] = mapped_column(ForeignKey("care_plans.id", ondelete="CASCADE"))
    day: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    replacement: Mapped[str] = mapped_column(String(120), default="")
    discomfort: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class FollowUpReminder(Base):
    __tablename__ = "follow_up_reminders"
    __table_args__ = (Index("uq_follow_up_reminders_plan", "plan_id", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"))
    plan_id: Mapped[str] = mapped_column(ForeignKey("care_plans.id", ondelete="CASCADE"))
    remind_on: Mapped[date] = mapped_column(Date)
    basis: Mapped[str] = mapped_column(String(16))
    note: Mapped[str] = mapped_column(String(240), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PlanRevision(Base):
    __tablename__ = "plan_revisions"
    __table_args__ = (
        Index("uq_plan_revisions_new_plan", "new_plan_id", unique=True),
        Index("uq_plan_revisions_old_plan", "old_plan_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"))
    old_plan_id: Mapped[str] = mapped_column(ForeignKey("care_plans.id", ondelete="CASCADE"))
    new_plan_id: Mapped[str] = mapped_column(ForeignKey("care_plans.id", ondelete="CASCADE"))
    new_report_id: Mapped[str] = mapped_column(ForeignKey("health_reports.id", ondelete="CASCADE"))
    changes: Mapped[list[dict]] = mapped_column(JSON)
    comparison: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
