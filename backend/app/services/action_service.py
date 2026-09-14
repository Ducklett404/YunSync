from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from app.core.action_policy import review_label, template_is_publishable
from app.core.config import settings
from app.integrations.huawei.maas import (
    ActionExplanationContext,
    MaaSError,
    get_maas_client,
)
from app.integrations.cache import cache
from app.models.action import ActionTemplate
from app.models.user import UserProfile
from app.repositories.action_repository import action_repository
from app.repositories.health_repository import health_repository
from app.services.explanation_policy import (
    ExplanationPolicyError,
    build_policy_fallback,
    validate_action_explanation,
)


RANKING_WEIGHTS = {
    "evidence": 0.40,
    "observability": 0.35,
    "ease": 0.25,
}
MIN_CONFIRMED_METRICS = 3


class ActionService:
    async def ranked_actions(self, db: Session, user_id: str) -> list[dict]:
        user = db.get(UserProfile, user_id)
        if user is None:
            raise LookupError("用户不存在")
        if user.high_risk or user.screening_status != "eligible":
            return []
        report = health_repository.latest_report(db, user_id)
        if report is None or report.status != "confirmed":
            return []
        metrics = health_repository.metrics_for_report(db, report.id)
        metric_codes = {metric.code for metric in metrics}
        if (
            len(metric_codes) < MIN_CONFIRMED_METRICS
            or any(not metric.confirmed for metric in metrics)
        ):
            return []

        ranked: list[dict] = []
        for action in action_repository.list_active(db):
            if not template_is_publishable(action, settings.environment):
                continue
            if self._has_contraindication(user, action):
                continue
            if action.signal_metric_codes and not metric_codes.intersection(
                action.signal_metric_codes
            ):
                continue

            components = self._score_components(action)
            explanation, explanation_source = await self._safe_explanation(action)
            ranked.append(
                {
                    "id": action.id,
                    "code": action.code,
                    "template_version": action.version,
                    "review_status": action.review_status,
                    "review_scope": action.review_scope,
                    "review_label": review_label(action.review_status),
                    "title": action.title,
                    "category": action.category,
                    "description": action.description,
                    "evidence_summary": action.evidence_summary,
                    "suitable_if": action.suitable_if,
                    "safety_note": action.safety_note,
                    "primary_metric": action.primary_metric,
                    "risk_level": action.risk_level,
                    "score": components["total"],
                    "score_components": components,
                    "ranking_policy_version": action.ranking_policy_version,
                    "rank_reason": (
                        f"依据 {components['evidence_points']:g} + "
                        f"可观察性 {components['observability_points']:g} + "
                        f"易执行性 {components['ease_points']:g} = "
                        f"{components['total']:g}；分数不是疗效概率。"
                    ),
                    "explanation": explanation,
                    "explanation_source": explanation_source,
                    "explanation_policy_version": action.explanation_policy_version,
                    "safety_checks": [
                        "安全初筛通过",
                        f"模板 {action.version} 状态有效",
                        f"{len(metric_codes)} 项不同报告指标已确认",
                        "行动风险级别为低风险",
                    ],
                }
            )
        return sorted(ranked, key=lambda item: (-item["score"], item["id"]))

    @staticmethod
    def _score_components(action: ActionTemplate) -> dict[str, float]:
        evidence_points = round(action.evidence_score * RANKING_WEIGHTS["evidence"] * 100, 1)
        observability_points = round(
            action.observability_score * RANKING_WEIGHTS["observability"] * 100, 1
        )
        ease_points = round((1 - action.effort_score) * RANKING_WEIGHTS["ease"] * 100, 1)
        return {
            "evidence_weight": RANKING_WEIGHTS["evidence"] * 100,
            "observability_weight": RANKING_WEIGHTS["observability"] * 100,
            "ease_weight": RANKING_WEIGHTS["ease"] * 100,
            "evidence_points": evidence_points,
            "observability_points": observability_points,
            "ease_points": ease_points,
            "total": round(evidence_points + observability_points + ease_points, 1),
        }

    @staticmethod
    def _has_contraindication(user: UserProfile, action: ActionTemplate) -> bool:
        answers = user.screening_answers or {}
        return any(answers.get(code, False) for code in action.contraindication_codes)

    @staticmethod
    async def _safe_explanation(action: ActionTemplate) -> tuple[str, str]:
        cache_key = cache.make_key(
            "action-explanation",
            action.id,
            action.version,
            action.explanation_policy_version,
        )
        cached = cache.get_json(cache_key) if cache.enabled else None
        if isinstance(cached, dict):
            cached_text = cached.get("text")
            cached_source = cached.get("source")
            if isinstance(cached_text, str) and cached_source in {
                "mock_maas",
                "huawei_maas",
                "policy_fallback",
            }:
                try:
                    return (
                        validate_action_explanation(
                            cached_text, action_title=action.title
                        ),
                        cached_source,
                    )
                except ExplanationPolicyError:
                    cache.delete(cache_key)
        client = get_maas_client()
        context = ActionExplanationContext(
            title=action.title,
            version=action.version,
            description=action.description,
            evidence_summary=action.evidence_summary,
            suitable_if=action.suitable_if,
            safety_note=action.safety_note,
            primary_metric=action.primary_metric,
        )
        try:
            generated = await asyncio.wait_for(
                client.explain_action(context), timeout=settings.maas_timeout_seconds
            )
            result = (
                validate_action_explanation(generated, action_title=action.title),
                client.provider,
            )
        except (MaaSError, ExplanationPolicyError, asyncio.TimeoutError):
            result = (
                build_policy_fallback(
                    action_title=action.title,
                    version=action.version,
                    primary_metric=action.primary_metric,
                ),
                "policy_fallback",
            )
        if cache.enabled:
            cache.set_json(cache_key, {"text": result[0], "source": result[1]})
        return result


action_service = ActionService()
