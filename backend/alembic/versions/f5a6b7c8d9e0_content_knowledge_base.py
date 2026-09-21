"""Add versioned content knowledge base.

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f5a6b7c8d9e0"
down_revision: str | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidence_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("publisher", sa.String(length=160), nullable=False),
        sa.Column("url_or_archive_ref", sa.String(length=500), nullable=False),
        sa.Column("published_on", sa.Date(), nullable=False),
        sa.Column("jurisdiction", sa.String(length=80), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'superseded', 'withdrawn')",
            name="ck_evidence_sources_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_evidence_sources_code_version",
        "evidence_sources",
        ["code", "version"],
        unique=True,
    )
    op.create_index(
        "idx_evidence_sources_status_title",
        "evidence_sources",
        ["status", "title"],
    )

    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("content_type", sa.String(length=24), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "content_type IN ('ingredient', 'recipe', 'contraindication')",
            name="ck_knowledge_items_content_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'reviewed', 'published', 'retired')",
            name="ck_knowledge_items_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_knowledge_items_type_code_version",
        "knowledge_items",
        ["content_type", "code", "version"],
        unique=True,
    )
    op.create_index(
        "uq_knowledge_items_active_version",
        "knowledge_items",
        ["content_type", "code"],
        unique=True,
        sqlite_where=sa.text("is_active = 1"),
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "idx_knowledge_items_type_status_title",
        "knowledge_items",
        ["content_type", "status", "title"],
    )

    op.create_table(
        "content_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reviewer_id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_qualification", sa.String(length=160), nullable=False),
        sa.Column("review_scope", sa.String(length=240), nullable=False),
        sa.Column("evidence_ref", sa.String(length=240), nullable=False),
        sa.Column("attested", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["knowledge_items.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected')",
            name="ck_content_reviews_decision",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_reviews_item_id", "content_reviews", ["item_id"])
    op.create_index(
        "idx_content_reviews_item_created",
        "content_reviews",
        ["item_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_content_reviews_item_created", table_name="content_reviews")
    op.drop_index("ix_content_reviews_item_id", table_name="content_reviews")
    op.drop_table("content_reviews")
    op.drop_index("idx_knowledge_items_type_status_title", table_name="knowledge_items")
    op.drop_index("uq_knowledge_items_active_version", table_name="knowledge_items")
    op.drop_index("uq_knowledge_items_type_code_version", table_name="knowledge_items")
    op.drop_table("knowledge_items")
    op.drop_index("idx_evidence_sources_status_title", table_name="evidence_sources")
    op.drop_index("uq_evidence_sources_code_version", table_name="evidence_sources")
    op.drop_table("evidence_sources")
