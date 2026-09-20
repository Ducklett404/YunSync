from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class HealthReport(Base):
    __tablename__ = "health_reports"
    __table_args__ = (
        Index("idx_health_reports_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(32), default="synthetic")
    status: Mapped[str] = mapped_column(String(32), default="needs_confirmation")
    critical_marker_status: Mapped[str] = mapped_column(String(16), default="unknown")
    critical_marker_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    storage_provider: Mapped[str] = mapped_column(String(32), default="local_private")
    storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(String(64), default="application/octet-stream")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    content_sha256: Mapped[str] = mapped_column(String(64), default="")
    ocr_provider: Mapped[str] = mapped_column(String(32), default="mock_ocr")
    ocr_status: Mapped[str] = mapped_column(String(24), default="pending")
    ocr_attempts: Mapped[int] = mapped_column(Integer, default=0)
    ocr_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ocr_page_count: Mapped[int] = mapped_column(Integer, default=0)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class HealthMetric(Base):
    __tablename__ = "health_metrics"
    __table_args__ = (
        Index(
            "uq_health_metrics_report_code",
            "report_id",
            "code",
            unique=True,
        ),
        Index("idx_health_metrics_report_name", "report_id", "name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    report_id: Mapped[str] = mapped_column(ForeignKey("health_reports.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(80))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    reference_range: Mapped[str] = mapped_column(String(64), default="")
    flag: Mapped[str] = mapped_column(String(16), default="normal")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    review_status: Mapped[str] = mapped_column(String(24), default="pending")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    extracted_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    extracted_unit: Mapped[str] = mapped_column(String(32), default="")
    extracted_reference_range: Mapped[str] = mapped_column(String(64), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source_page: Mapped[int] = mapped_column(Integer, default=1)
    source_bbox: Mapped[list[float]] = mapped_column(JSON, default=lambda: [0.0, 0.0, 1.0, 1.0])
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
