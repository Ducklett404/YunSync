from __future__ import annotations

from typing import Protocol


RANKING_POLICY_VERSION = "rank-v1"
EXPLANATION_POLICY_VERSION = "action-explain-v1"
PROTOTYPE_REVIEW_STATUS = "prototype_approved"
PROFESSIONAL_REVIEW_STATUS = "professionally_approved"


class GovernedTemplate(Protocol):
    is_active: bool
    review_status: str
    risk_level: str


def template_is_publishable(template: GovernedTemplate, environment: str) -> bool:
    allowed_statuses = (
        {PROFESSIONAL_REVIEW_STATUS}
        if environment == "production"
        else {PROTOTYPE_REVIEW_STATUS, PROFESSIONAL_REVIEW_STATUS}
    )
    return (
        template.is_active
        and template.review_status in allowed_statuses
        and template.risk_level == "low"
    )


def review_label(review_status: str) -> str:
    if review_status == PROFESSIONAL_REVIEW_STATUS:
        return "专业审核通过"
    if review_status == PROTOTYPE_REVIEW_STATUS:
        return "产品规则校验（待专业复核）"
    return "未发布"
