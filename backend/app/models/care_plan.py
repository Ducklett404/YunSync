from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CarePlan(Base):
    __tablename__ = "care_plans"
    __table_args__ = (
        CheckConstraint("status IN ('READY', 'ACTIVE', 'PAUSED')", name="ck_care_plans_status"),
        Index("idx_care_plans_user_created", "user_id", "created_at"),
        Index("uq_care_plans_user_request", "user_id", "request_hash", unique=True),
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
