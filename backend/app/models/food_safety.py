from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FoodSafetyProfile(Base):
    __tablename__ = "food_safety_profiles"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    allergy_status: Mapped[str] = mapped_column(String(16), default="unknown")
    allergens: Mapped[list[str]] = mapped_column(JSON, default=list)
    medication_status: Mapped[str] = mapped_column(String(16), default="unknown")
    medications: Mapped[list[str]] = mapped_column(JSON, default=list)
    condition_status: Mapped[str] = mapped_column(String(16), default="unknown")
    conditions: Mapped[list[str]] = mapped_column(JSON, default=list)
    clinician_restriction_status: Mapped[str] = mapped_column(String(16), default="unknown")
    clinician_restrictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    special_status: Mapped[str] = mapped_column(String(24), default="unknown")
    special_details: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
