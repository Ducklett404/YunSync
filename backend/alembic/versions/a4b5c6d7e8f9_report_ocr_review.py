"""report OCR and field review workflow

Revision ID: a4b5c6d7e8f9
Revises: 8c1d2e3f4a5b
Create Date: 2026-09-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, None] = "8c1d2e3f4a5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "health_reports",
        sa.Column("storage_provider", sa.String(length=32), server_default="legacy", nullable=False),
    )
    op.add_column("health_reports", sa.Column("storage_key", sa.String(length=255), nullable=True))
    op.add_column(
        "health_reports",
        sa.Column(
            "content_type",
            sa.String(length=64),
            server_default="application/octet-stream",
            nullable=False,
        ),
    )
    op.add_column(
        "health_reports", sa.Column("file_size", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "health_reports",
        sa.Column("content_sha256", sa.String(length=64), server_default="", nullable=False),
    )
    op.add_column(
        "health_reports",
        sa.Column("ocr_provider", sa.String(length=32), server_default="legacy", nullable=False),
    )
    op.add_column(
        "health_reports",
        sa.Column("ocr_status", sa.String(length=24), server_default="completed", nullable=False),
    )
    op.add_column(
        "health_reports", sa.Column("ocr_attempts", sa.Integer(), server_default="1", nullable=False)
    )
    op.add_column(
        "health_reports", sa.Column("ocr_error_code", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "health_reports",
        sa.Column("ocr_page_count", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column("health_reports", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "idx_health_reports_user_created",
        "health_reports",
        ["user_id", "created_at"],
        unique=False,
    )

    op.add_column(
        "health_metrics",
        sa.Column("review_status", sa.String(length=24), server_default="pending", nullable=False),
    )
    op.add_column(
        "health_metrics", sa.Column("raw_text", sa.Text(), server_default="", nullable=False)
    )
    op.add_column("health_metrics", sa.Column("extracted_value", sa.Float(), nullable=True))
    op.add_column(
        "health_metrics",
        sa.Column("extracted_unit", sa.String(length=32), server_default="", nullable=False),
    )
    op.add_column(
        "health_metrics",
        sa.Column(
            "extracted_reference_range",
            sa.String(length=64),
            server_default="",
            nullable=False,
        ),
    )
    op.add_column(
        "health_metrics", sa.Column("confidence", sa.Float(), server_default="1", nullable=False)
    )
    op.add_column(
        "health_metrics", sa.Column("source_page", sa.Integer(), server_default="1", nullable=False)
    )
    op.add_column(
        "health_metrics",
        sa.Column(
            "source_bbox", sa.JSON(), server_default=sa.text("'[0,0,1,1]'"), nullable=False
        ),
    )
    op.execute(
        sa.text(
            "UPDATE health_metrics SET review_status = 'confirmed' WHERE confirmed = :confirmed"
        ).bindparams(confirmed=True)
    )


def downgrade() -> None:
    op.drop_column("health_metrics", "source_bbox")
    op.drop_column("health_metrics", "source_page")
    op.drop_column("health_metrics", "confidence")
    op.drop_column("health_metrics", "extracted_reference_range")
    op.drop_column("health_metrics", "extracted_unit")
    op.drop_column("health_metrics", "extracted_value")
    op.drop_column("health_metrics", "raw_text")
    op.drop_column("health_metrics", "review_status")

    op.drop_index("idx_health_reports_user_created", table_name="health_reports")
    op.drop_column("health_reports", "processed_at")
    op.drop_column("health_reports", "ocr_page_count")
    op.drop_column("health_reports", "ocr_error_code")
    op.drop_column("health_reports", "ocr_attempts")
    op.drop_column("health_reports", "ocr_status")
    op.drop_column("health_reports", "ocr_provider")
    op.drop_column("health_reports", "content_sha256")
    op.drop_column("health_reports", "file_size")
    op.drop_column("health_reports", "content_type")
    op.drop_column("health_reports", "storage_key")
    op.drop_column("health_reports", "storage_provider")
