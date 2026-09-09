from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ActionTemplate(Base):
    __tablename__ = "action_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
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

