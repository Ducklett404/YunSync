from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PrivacyRequest(Base):
    __tablename__ = "privacy_requests"
    __table_args__ = (
        CheckConstraint(
            "request_type IN ('account_deletion')",
            name="ck_privacy_requests_type",
        ),
        CheckConstraint(
            "status IN ('pending','cancelled','completed')",
            name="ck_privacy_requests_status",
        ),
        Index(
            "uq_privacy_requests_pending_subject_type",
            "subject_hash",
            "request_type",
            unique=True,
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
        Index("idx_privacy_requests_due", "status", "execute_after"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    subject_hash: Mapped[str] = mapped_column(String(64), index=True)
    request_type: Mapped[str] = mapped_column(String(32), default="account_deletion")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    execute_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
