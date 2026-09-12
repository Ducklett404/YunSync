from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Experiment(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','paused','terminated','completed')",
            name="ck_experiments_status",
        ),
        Index(
            "uq_experiments_active_user",
            "user_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        Index("idx_experiments_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"), index=True)
    action_id: Mapped[str] = mapped_column(ForeignKey("action_templates.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="active")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    randomization_seed: Mapped[int] = mapped_column(Integer)
    schedule: Mapped[list] = mapped_column(JSON)
    schedule_version: Mapped[str] = mapped_column(
        String(32), default="balanced-14-v1"
    )
    schedule_hash: Mapped[str] = mapped_column(String(64))
    schedule_locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    terminated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_step: Mapped[str | None] = mapped_column(String(24), nullable=True)
    next_step_selected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (UniqueConstraint("experiment_id", "observed_on", name="uq_experiment_day"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), index=True)
    observed_on: Mapped[date] = mapped_column(Date)
    treatment: Mapped[bool] = mapped_column(Boolean)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    steps_30m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    sugary_drinks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subjective_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    missing_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    discomfort_level: Mapped[str] = mapped_column(String(16), default="none")
    discomfort_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    unplanned_event: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
