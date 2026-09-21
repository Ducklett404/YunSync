from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, Text, text
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
    liver_kidney_status: Mapped[str] = mapped_column(String(16), default="unknown")
    liver_kidney_conditions: Mapped[list[str]] = mapped_column(JSON, default=list)
    clinician_restriction_status: Mapped[str] = mapped_column(String(16), default="unknown")
    clinician_restrictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    special_status: Mapped[str] = mapped_column(String(24), default="unknown")
    special_details: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class SafetyRuleRelease(Base):
    __tablename__ = "safety_rule_releases"
    __table_args__ = (
        Index("uq_safety_rule_releases_version", "version", unique=True),
        Index(
            "uq_safety_rule_releases_published",
            "status",
            unique=True,
            sqlite_where=text("status = 'published'"),
            postgresql_where=text("status = 'published'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="published")
    evidence_ref: Mapped[str] = mapped_column(String(240))
    reviewer_qualification: Mapped[str] = mapped_column(String(160))
    reviewed_rule_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    attested: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewer_id: Mapped[str] = mapped_column(String(36))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
