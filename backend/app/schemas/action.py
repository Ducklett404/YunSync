from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    template_version: str
    review_status: str
    review_scope: str
    review_label: str
    title: str
    category: str
    description: str
    evidence_summary: str
    suitable_if: str
    safety_note: str
    primary_metric: str
    risk_level: str
    score: float
    score_components: dict[str, float]
    ranking_policy_version: str
    rank_reason: str
    explanation: str
    explanation_source: str
    explanation_policy_version: str
    safety_checks: list[str]


class ActionTemplateAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    version: str
    title: str
    category: str
    risk_level: str
    review_status: str
    review_scope: str
    reviewer_ref: str | None
    reviewed_at: datetime | None
    is_active: bool
    deactivated_at: datetime | None
    contraindication_codes: list[str]
    signal_metric_codes: list[str]
    ranking_policy_version: str
    explanation_policy_version: str


class ActionTemplateVersionCreate(BaseModel):
    version: str = Field(
        min_length=1,
        max_length=32,
        pattern=r"^[0-9A-Za-z][0-9A-Za-z._-]{0,31}$",
    )


class ActionTemplateStatusUpdate(BaseModel):
    review_status: Literal["draft", "prototype_approved", "retired"]
    is_active: bool
