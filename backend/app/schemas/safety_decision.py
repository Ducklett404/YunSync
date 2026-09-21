from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SafetyDecisionOut(BaseModel):
    decision: Literal[
        "urgent_care",
        "consult_professional",
        "complete_information",
        "awaiting_review_rules",
        "ready_general_guidance",
    ]
    tier: Literal["A", "B", "C"] | None
    can_generate_plan: bool
    rule_version: str
    message: str
    missing_items: list[str]


class SafetyRuleReleaseIn(BaseModel):
    version: str = Field(min_length=3, max_length=40, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]+$")
    evidence_ref: str = Field(min_length=3, max_length=240)
    reviewer_qualification: str = Field(min_length=3, max_length=160)
    reviewed_rule_codes: list[str] = Field(min_length=1, max_length=30)
    attested: Literal[True]

    @field_validator("evidence_ref", "reviewer_qualification")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("reviewed_rule_codes")
    @classmethod
    def normalize_codes(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("审核规则代码不能为空或重复")
        return sorted(normalized)


class SafetyRuleReleaseOut(BaseModel):
    id: str
    version: str
    status: Literal["published", "retired"]
    evidence_ref: str
    reviewer_qualification: str
    reviewed_rule_codes: list[str]
    attested: bool
    reviewer_id: str
    published_at: datetime
    retired_at: datetime | None

    model_config = {"from_attributes": True}
