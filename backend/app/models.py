from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    servings: Mapped[int] = mapped_column(Integer, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    ingredients: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    tools: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    substitutions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    allergens: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    exclusions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    regions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    scene_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_note: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(180), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    version: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    content_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class SeasonalContent(Base):
    __tablename__ = "seasonal_contents"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    culture_note: Mapped[str] = mapped_column(Text, nullable=False)
    date_rule: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    regions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    recipe_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(180), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    version: Mapped[str] = mapped_column(String(60), nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    content_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RecommendationAudit(Base):
    __tablename__ = "recommendation_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    rule_version: Mapped[str] = mapped_column(String(40), nullable=False)
    candidate_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    selected_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    degraded_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )
