from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(80), default="演示用户")
    role: Mapped[str] = mapped_column(String(20), default="participant")
    age_range: Mapped[str] = mapped_column(String(20), default="25-34")
    goal: Mapped[str] = mapped_column(String(120), default="改善日常活动习惯")
    sleep_schedule: Mapped[str] = mapped_column(String(120), default="")
    activity_baseline: Mapped[str] = mapped_column(String(160), default="")
    constraints: Mapped[str] = mapped_column(Text, default="")
    preferences: Mapped[str] = mapped_column(Text, default="")
    high_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    screening_status: Mapped[str] = mapped_column(String(32), default="pending")
    screening_answers: Mapped[dict] = mapped_column(JSON, default=dict)
    screened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
