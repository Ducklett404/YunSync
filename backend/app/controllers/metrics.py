"""Read-only confirmed metric history for the current participant."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_active_participant
from app.db.session import get_db
from app.models.user import UserProfile
from app.schemas.metric_history import MetricHistoryOut
from app.services.metric_history_service import metric_history


router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary", response_model=MetricHistoryOut)
def get_metric_summary(
    report_limit: int = Query(default=20, ge=1, le=50),
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    return metric_history(db, user.id, report_limit=report_limit)
