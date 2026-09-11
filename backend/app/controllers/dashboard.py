from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import require_active_participant
from app.models.action import ActionTemplate
from app.models.user import UserProfile
from app.repositories.experiment_repository import experiment_repository
from app.repositories.health_repository import health_repository
from app.services.action_service import action_service
from app.services.experiment_service import experiment_service


router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def get_dashboard(
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    user_id = user.id

    report = health_repository.latest_report(db, user_id)
    metrics = health_repository.metrics_for_report(db, report.id) if report else []
    experiment = experiment_repository.latest_for_user(db, user_id)
    experiment_payload = None
    if experiment:
        action = db.get(ActionTemplate, experiment.action_id)
        observations = experiment_repository.observations(db, experiment.id)
        completed_dates = {
            item.observed_on.isoformat() for item in observations if item.completed
        }
        experiment_payload = {
            "id": experiment.id,
            "action_id": experiment.action_id,
            "action_code": action.code if action else "unknown",
            "action_title": action.title if action else "未知行动",
            "primary_metric": action.primary_metric if action else "未知指标",
            "status": experiment.status,
            "start_date": experiment.start_date,
            "end_date": experiment.end_date,
            "progress": len([item for item in observations if item.completed]),
            "schedule": [
                {**day, "completed": day["date"] in completed_dates}
                for day in experiment.schedule
            ],
            "result": experiment_service.result(db, experiment.id),
        }

    return {
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "age_range": user.age_range,
            "goal": user.goal,
            "high_risk": user.high_risk,
        },
        "report": {
            "id": report.id,
            "filename": report.filename,
            "status": report.status,
            "source": report.source,
        } if report else None,
        "metrics": [
            {
                "id": metric.id,
                "code": metric.code,
                "name": metric.name,
                "value": metric.value,
                "unit": metric.unit,
                "reference_range": metric.reference_range,
                "flag": metric.flag,
                "confirmed": metric.confirmed,
                "review_status": metric.review_status,
                "raw_text": metric.raw_text,
                "extracted_value": metric.extracted_value,
                "extracted_unit": metric.extracted_unit,
                "extracted_reference_range": metric.extracted_reference_range,
                "confidence": metric.confidence,
                "source_page": metric.source_page,
                "source_bbox": metric.source_bbox,
            }
            for metric in metrics
        ],
        "experiment": experiment_payload,
        "actions": (await action_service.ranked_actions(db, user_id))[:3],
        "notice": "当前页面使用合成数据，仅用于产品演示。",
    }
