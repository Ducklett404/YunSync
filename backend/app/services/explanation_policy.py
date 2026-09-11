from __future__ import annotations

import re

from app.core.action_policy import EXPLANATION_POLICY_VERSION


FORBIDDEN_PATTERNS = (
    re.compile(r"(你|用户|该结果).{0,12}(确诊|患有|得了|证明.{0,6}疾病)"),
    re.compile(r"(停药|停服|自行增减|调整药物|修改剂量|更改剂量)"),
    re.compile(r"(连续断食|完全禁食|极端节食|高强度运动|每天运动.{0,4}(2|3|两|三)小时)"),
    re.compile(r"(保证有效|一定有效|治愈|逆转疾病)"),
)


class ExplanationPolicyError(ValueError):
    pass


def build_policy_fallback(
    *, action_title: str, version: str, primary_metric: str
) -> str:
    return (
        f"“{action_title}”来自行动模板 {version}。"
        "适配分只比较依据质量、执行负担和短期可观测性；"
        f"本轮主要观察“{primary_metric}”。"
        "开始前请核对适用条件和安全说明，本说明不构成诊断或治疗建议。"
    )


def validate_action_explanation(text: str, *, action_title: str) -> str:
    normalized = " ".join(text.split())
    if len(normalized) < 20 or len(normalized) > 240:
        raise ExplanationPolicyError("解释长度不符合策略")
    if action_title not in normalized:
        raise ExplanationPolicyError("解释缺少行动名称")
    if any(pattern.search(normalized) for pattern in FORBIDDEN_PATTERNS):
        raise ExplanationPolicyError("解释触发诊断、调药或极端方案守卫")
    return normalized


def build_policy_fallback(
    *, action_title: str, version: str, primary_metric: str
) -> str:
    return (
        f"“{action_title}”来自合成行动模板 {version}。"
        "适配分只用于比较依据质量、执行负担和短期可观测性，"
        f"主要观察“{primary_metric}”。开始前请核对适用条件和安全说明；"
        "该说明不构成诊断、治疗或药物调整建议。"
    )


__all__ = [
    "EXPLANATION_POLICY_VERSION",
    "ExplanationPolicyError",
    "build_policy_fallback",
    "validate_action_explanation",
]
