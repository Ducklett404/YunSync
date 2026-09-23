"""Participant-only comparison of two confirmed report batches."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_active_participant
from app.db.session import get_db
from app.models.user import UserProfile
from app.schemas.care_plan import FollowUpCompareIn
from app.schemas.follow_up import FollowUpComparisonOut
from app.services.follow_up_service import FollowUpConflict, compare_reports


router = APIRouter(prefix="/follow-ups", tags=["follow-ups"])


@router.post("/compare", response_model=FollowUpComparisonOut)
def compare(
    payload: FollowUpCompareIn,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        return compare_reports(db, user.id, payload.previous_report_id, payload.current_report_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FollowUpConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
