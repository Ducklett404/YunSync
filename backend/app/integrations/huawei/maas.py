from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


class MaaSError(RuntimeError):
    pass


@dataclass(frozen=True)
class ActionExplanationContext:
    title: str
    version: str
    description: str
    evidence_summary: str
    suitable_if: str
    safety_note: str
    primary_metric: str


@dataclass(frozen=True)
class ResultExplanationContext:
    metric_label: str
    metric_unit: str
    status: str
    message: str
    valid_days: int
    missing_days: int
    bootstrap_ci_lower: float | None
    bootstrap_ci_upper: float | None
    recommended_next_step: str


class MockMaaSClient:
    provider = "mock_maas"

    async def explain_action(self, context: ActionExplanationContext) -> str:
        return (
            f"“{context.title}”来自合成行动模板 {context.version}。"
            "当前适配分只比较依据质量、执行负担和短期可观测性；"
            f"开始前请核对适用条件与安全说明，主要观察“{context.primary_metric}”。"
            "本说明仅用于选择低风险行为实验，不构成诊断或治疗建议。"
        )

    async def explain_result(self, context: ResultExplanationContext) -> str:
        if context.status == "data_insufficient":
            detail = (
                f"目前共有 {context.valid_days} 天有效记录、{context.missing_days} 天缺少主要指标，"
                "提醒日或常规日样本不足，所以不能判断观察方向。"
            )
        else:
            detail = (
                f"{context.message} 95% 重采样区间为 "
                f"{context.bootstrap_ci_lower:+g} 至 {context.bootstrap_ci_upper:+g} "
                f"{context.metric_unit}，区间用于表达这轮小样本的不确定性。"
            )
        return (
            f"本轮主要观察{context.metric_label}。{detail}"
            "这些结果只适用于当前个人与观察周期，不构成诊断或治疗建议。"
        )


class HuaweiMaaSClient:
    provider = "huawei_maas"

    async def explain_action(self, _context: ActionExplanationContext) -> str:
        raise MaaSError(
            "华为云 MaaS 适配器尚未配置，不能将模板解释冒充真实模型输出。"
        )

    async def explain_result(self, _context: ResultExplanationContext) -> str:
        raise MaaSError(
            "华为云 MaaS 适配器尚未配置，不能将结果解释冒充真实模型输出。"
        )


def get_maas_client():
    if settings.use_mock_ai:
        return MockMaaSClient()
    return HuaweiMaaSClient()
