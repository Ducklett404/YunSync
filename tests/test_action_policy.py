from types import SimpleNamespace

import pytest

from app.core.action_policy import template_is_publishable
from app.services.explanation_policy import (
    ExplanationPolicyError,
    build_policy_fallback,
    validate_action_explanation,
)


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "“饭后轻量活动提醒”证明你患有某种疾病，应立即处理。",
        "“饭后轻量活动提醒”建议自行调整药物并修改剂量。",
        "“饭后轻量活动提醒”要求连续断食并开展高强度运动。",
        "“饭后轻量活动提醒”保证有效，可以治愈相关问题。",
    ],
)
def test_explanation_policy_rejects_diagnosis_medication_and_extreme_claims(
    unsafe_text,
):
    with pytest.raises(ExplanationPolicyError):
        validate_action_explanation(unsafe_text, action_title="饭后轻量活动提醒")


def test_policy_fallback_passes_the_same_output_validator():
    fallback = build_policy_fallback(
        action_title="饭后轻量活动提醒",
        version="1.0.0",
        primary_metric="饭后 30 分钟步数",
    )

    assert (
        validate_action_explanation(
            fallback, action_title="饭后轻量活动提醒"
        )
        == fallback
    )


@pytest.mark.parametrize(
    ("environment", "status", "expected"),
    [
        ("development", "prototype_approved", True),
        ("production", "prototype_approved", False),
        ("production", "professionally_approved", True),
    ],
)
def test_publishable_template_status_depends_on_environment(
    environment, status, expected
):
    template = SimpleNamespace(
        is_active=True,
        review_status=status,
        risk_level="low",
    )

    assert template_is_publishable(template, environment) is expected
