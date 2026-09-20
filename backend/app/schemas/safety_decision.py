from typing import Literal

from pydantic import BaseModel


class SafetyDecisionOut(BaseModel):
    decision: Literal[
        "urgent_care",
        "consult_professional",
        "complete_information",
        "awaiting_review_rules",
    ]
    tier: Literal["B", "C"] | None
    can_generate_plan: bool
    rule_version: str
    message: str
    missing_items: list[str]
