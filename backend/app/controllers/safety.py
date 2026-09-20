from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_active_participant
from app.db.session import get_db
from app.models.user import UserProfile
from app.schemas.safety_decision import SafetyDecisionOut
from app.services.safety_decision_service import evaluate_safety


router = APIRouter(prefix="/safety", tags=["safety"])


@router.get("/decision", response_model=SafetyDecisionOut)
def safety_decision(
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    return evaluate_safety(db, user)
