from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(80), default="演示用户")
    age_range: Mapped[str] = mapped_column(String(20), default="25-34")
    goal: Mapped[str] = mapped_column(String(120), default="改善日常活动习惯")
    high_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

