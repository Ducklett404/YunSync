from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ActionTemplate(Base):
    __tablename__ = "action_templates"
    __table_args__ = (
        Index("uq_action_templates_code_version", "code", "version", unique=True),
        Index(
            "uq_action_templates_active_code",
            "code",
            unique=True,
            sqlite_where=text("is_active = 1"),
            postgresql_where=text("is_active = true"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    title: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    evidence_summary: Mapped[str] = mapped_column(Text)
    suitable_if: Mapped[str] = mapped_column(Text)
    safety_note: Mapped[str] = mapped_column(Text)
    primary_metric: Mapped[str] = mapped_column(String(120))
    evidence_score: Mapped[float] = mapped_column(Float, default=0.7)
    effort_score: Mapped[float] = mapped_column(Float, default=0.5)
    observability_score: Mapped[float] = mapped_column(Float, default=0.8)
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    review_status: Mapped[str] = mapped_column(String(32), default="draft")
    review_scope: Mapped[str] = mapped_column(String(32), default="prototype_rules")
    reviewer_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    contraindication_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    signal_metric_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    ranking_policy_version: Mapped[str] = mapped_column(String(32), default="rank-v1")
    explanation_policy_version: Mapped[str] = mapped_column(
        String(32), default="action-explain-v1"
    )
