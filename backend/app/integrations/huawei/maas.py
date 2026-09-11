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


class MockMaaSClient:
    provider = "mock_maas"

    async def explain_action(self, context: ActionExplanationContext) -> str:
        return (
            f"“{context.title}”来自合成行动模板 {context.version}。"
            "当前适配分只比较依据质量、执行负担和短期可观测性；"
            f"开始前请核对适用条件与安全说明，主要观察“{context.primary_metric}”。"
            "本说明仅用于选择低风险行为实验，不构成诊断或治疗建议。"
        )


class HuaweiMaaSClient:
    provider = "huawei_maas"

    async def explain_action(self, _context: ActionExplanationContext) -> str:
        raise MaaSError(
            "华为云 MaaS 适配器尚未配置，不能将模板解释冒充真实模型输出。"
        )


def get_maas_client():
    if settings.use_mock_ai:
        return MockMaaSClient()
    return HuaweiMaaSClient()
