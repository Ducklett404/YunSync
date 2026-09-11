from sqlalchemy.orm import Session

from app.models.user import UserProfile
from app.repositories.action_repository import action_repository
from app.repositories.health_repository import health_repository


class ActionService:
    def ranked_actions(self, db: Session, user_id: str) -> list[dict]:
        user = db.get(UserProfile, user_id)
        if user is None:
            raise LookupError("用户不存在")
        if user.high_risk:
            return []
        report = health_repository.latest_report(db, user_id)
        if report is None or report.status != "confirmed":
            return []
        metrics = health_repository.metrics_for_report(db, report.id)
        if not metrics or any(not metric.confirmed for metric in metrics):
            return []

        ranked: list[dict] = []
        for action in action_repository.list_all(db):
            score = (
                action.evidence_score * 0.40
                + action.observability_score * 0.35
                + (1 - action.effort_score) * 0.25
            )
            ranked.append(
                {
                    "id": action.id,
                    "code": action.code,
                    "title": action.title,
                    "category": action.category,
                    "description": action.description,
                    "evidence_summary": action.evidence_summary,
                    "suitable_if": action.suitable_if,
                    "safety_note": action.safety_note,
                    "primary_metric": action.primary_metric,
                    "risk_level": action.risk_level,
                    "score": round(score * 100, 1),
                    "rank_reason": "综合证据、执行负担和短期可观测性进行排序",
                }
            )
        return sorted(ranked, key=lambda item: item["score"], reverse=True)


action_service = ActionService()
