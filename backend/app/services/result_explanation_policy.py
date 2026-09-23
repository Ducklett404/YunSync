from __future__ import annotations

import re

from app.services.result_analysis import RESULT_EXPLANATION_POLICY_VERSION


FORBIDDEN_RESULT_PATTERNS = (
    re.compile(r"(确诊|治愈|逆转疾病|证明.{0,8}(疾病|疗效))"),
    re.compile(r"(停药|停服|自行增减|调整药物|修改剂量|更改剂量)"),
    re.compile(r"(保证有效|一定有效|必然有效|适用于所有人)"),
    re.compile(r"(忽略|绕过).{0,12}(系统|指令|规则|限制)"),
    re.compile(r"(系统提示词|开发者消息|输出.{0,8}(密钥|口令|令牌)|泄露.{0,8}(隐私|凭据))", re.I),
)
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:\.\d+)?")
CHINESE_NUMBER_PATTERN = re.compile(r"[零〇一二两三四五六七八九十百千万]+")


class ResultExplanationPolicyError(ValueError):
    pass


def validate_result_explanation(
    text: str,
    *,
    metric_label: str,
    data_insufficient: bool,
    allowed_numeric_sources: tuple[str, ...] | None = None,
) -> str:
    normalized = " ".join(text.split())
    if len(normalized) < 40 or len(normalized) > 420:
        raise ResultExplanationPolicyError("复盘解释长度不符合策略")
    if metric_label not in normalized:
        raise ResultExplanationPolicyError("复盘解释缺少主要指标")
    if "不构成诊断或治疗建议" not in normalized:
        raise ResultExplanationPolicyError("复盘解释缺少安全边界")
    if any(pattern.search(normalized) for pattern in FORBIDDEN_RESULT_PATTERNS):
        raise ResultExplanationPolicyError("复盘解释触发诊断、调药或疗效保证守卫")
    if data_insufficient and re.search(r"(说明|证明|显示).{0,8}(有效|更好|改善)", normalized):
        raise ResultExplanationPolicyError("数据不足时不能给出方向性结论")
    if allowed_numeric_sources is not None:
        allowed = {95.0}
        allowed.update(
            float(match.group())
            for source in allowed_numeric_sources
            for match in NUMBER_PATTERN.finditer(str(source))
        )
        generated = {
            float(match.group()) for match in NUMBER_PATTERN.finditer(normalized)
        }
        allowed_chinese = {
            match.group()
            for source in allowed_numeric_sources
            for match in CHINESE_NUMBER_PATTERN.finditer(str(source))
        }
        generated_chinese = {
            match.group() for match in CHINESE_NUMBER_PATTERN.finditer(normalized)
        }
        if generated - allowed or generated_chinese - allowed_chinese:
            raise ResultExplanationPolicyError("复盘解释包含输入中不存在的数值")
    return normalized


def build_result_fallback(analysis: dict) -> str:
    metric_label = analysis["metric_label"]
    if analysis["status"] == "data_insufficient":
        lead = (
            f"{metric_label}的提醒日或常规日有效记录不足，当前不能判断观察方向。"
            "建议继续记录，并优先补齐缺失原因。"
        )
    else:
        lead = (
            f"{analysis['message']} 95% 重采样区间为 "
            f"{analysis['bootstrap_ci_lower']:+g} 至 {analysis['bootstrap_ci_upper']:+g} "
            f"{analysis['metric_unit']}，区间反映这轮小样本的不确定性。"
        )
    return f"{lead} 结果只适用于当前个人和观察周期，不构成诊断或治疗建议。"


__all__ = [
    "RESULT_EXPLANATION_POLICY_VERSION",
    "ResultExplanationPolicyError",
    "build_result_fallback",
    "validate_result_explanation",
]
