from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.experiment_policy import ScheduleIntegrityError
from app.db.session import get_db
from app.core.security import require_active_participant
from app.models.user import UserProfile
from app.repositories.experiment_repository import experiment_repository
from app.repositories.health_repository import health_repository
from app.services.action_service import action_service
from app.services.experiment_service import experiment_service
from app.services.result_review_service import result_review_service


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
        try:
            result = await result_review_service.explain(
                experiment_service.result(db, experiment.id)
            )
            experiment_payload = {
                **experiment_service.snapshot(db, experiment),
                "result": result,
            }
        except ScheduleIntegrityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

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
