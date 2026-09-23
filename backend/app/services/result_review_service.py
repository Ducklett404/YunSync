from __future__ import annotations

import asyncio

from app.core.config import settings
from app.integrations.huawei.maas import (
    MaaSError,
    ResultExplanationContext,
    get_maas_client,
)
from app.services.result_explanation_policy import (
    RESULT_EXPLANATION_POLICY_VERSION,
    ResultExplanationPolicyError,
    build_result_fallback,
    validate_result_explanation,
)


class ResultReviewService:
    async def explain(self, analysis: dict) -> dict:
        client = get_maas_client()
        context = ResultExplanationContext(
            metric_label=analysis["metric_label"],
            metric_unit=analysis["metric_unit"],
            status=analysis["status"],
            message=analysis["message"],
            valid_days=analysis["valid_days"],
            missing_days=analysis["missing_days"],
            bootstrap_ci_lower=analysis["bootstrap_ci_lower"],
            bootstrap_ci_upper=analysis["bootstrap_ci_upper"],
            recommended_next_step=analysis["recommended_next_step"],
        )
        try:
            generated = await asyncio.wait_for(
                client.explain_result(context),
                timeout=settings.maas_timeout_seconds,
            )
            explanation = validate_result_explanation(
                generated,
                metric_label=analysis["metric_label"],
                data_insufficient=analysis["status"] == "data_insufficient",
                allowed_numeric_sources=tuple(
                    str(value)
                    for value in (
                        context.metric_label,
                        context.metric_unit,
                        context.message,
                        context.valid_days,
                        context.missing_days,
                        context.bootstrap_ci_lower,
                        context.bootstrap_ci_upper,
                    )
                    if value is not None
                ),
            )
            source = client.provider
        except (MaaSError, ResultExplanationPolicyError, asyncio.TimeoutError):
            explanation = build_result_fallback(analysis)
            source = "policy_fallback"
        return {
            **analysis,
            "explanation": explanation,
            "explanation_source": source,
            "explanation_policy_version": RESULT_EXPLANATION_POLICY_VERSION,
        }


result_review_service = ResultReviewService()
