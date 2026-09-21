from datetime import date, datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'superseded', 'withdrawn')",
            name="ck_evidence_sources_status",
        ),
        Index("uq_evidence_sources_code_version", "code", "version", unique=True),
        Index("idx_evidence_sources_status_title", "status", "title"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(240))
    publisher: Mapped[str] = mapped_column(String(160))
    url_or_archive_ref: Mapped[str] = mapped_column(String(500))
    published_on: Mapped[date] = mapped_column(Date)
    jurisdiction: Mapped[str] = mapped_column(String(80))
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="active")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    @property
    def ref(self) -> str:
        return f"{self.code}@{self.version}"


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"
    __table_args__ = (
        CheckConstraint(
            "content_type IN ('ingredient', 'recipe', 'contraindication')",
            name="ck_knowledge_items_content_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'reviewed', 'published', 'retired')",
            name="ck_knowledge_items_status",
        ),
        Index(
            "uq_knowledge_items_type_code_version",
            "content_type",
            "code",
            "version",
            unique=True,
        ),
        Index(
            "uq_knowledge_items_active_version",
            "content_type",
            "code",
            unique=True,
            sqlite_where=text("is_active = 1"),
            postgresql_where=text("is_active = true"),
        ),
        Index("idx_knowledge_items_type_status_title", "content_type", "status", "title"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(24))
    code: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(160))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(36), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ContentReview(Base):
    __tablename__ = "content_reviews"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved', 'rejected')",
            name="ck_content_reviews_decision",
        ),
        Index("idx_content_reviews_item_created", "item_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(String(16))
    reviewer_id: Mapped[str] = mapped_column(String(36))
    reviewer_qualification: Mapped[str] = mapped_column(String(160))
    review_scope: Mapped[str] = mapped_column(String(240))
    evidence_ref: Mapped[str] = mapped_column(String(240))
    attested: Mapped[bool] = mapped_column(Boolean)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
