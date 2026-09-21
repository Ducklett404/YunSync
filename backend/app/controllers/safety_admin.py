from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import UserProfile
from app.schemas.safety_decision import SafetyRuleReleaseIn, SafetyRuleReleaseOut
from app.services.safety_rule_service import (
    SafetyRuleConflictError,
    list_safety_releases,
    publish_safety_release,
    retire_safety_release,
)


router = APIRouter(prefix="/admin/safety-rules", tags=["safety-rule-admin"])


@router.get("", response_model=list[SafetyRuleReleaseOut])
def list_releases(
    _reviewer: UserProfile = Depends(require_permission("safety_rules:publish")),
    db: Session = Depends(get_db),
):
    return list_safety_releases(db)


@router.post("", response_model=SafetyRuleReleaseOut)
def publish_release(
    payload: SafetyRuleReleaseIn,
    reviewer: UserProfile = Depends(require_permission("safety_rules:publish")),
    db: Session = Depends(get_db),
):
    try:
        return publish_safety_release(db, payload, reviewer.id)
    except SafetyRuleConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/{release_id}/retire", response_model=SafetyRuleReleaseOut)
def retire_release(
    release_id: str,
    reviewer: UserProfile = Depends(require_permission("safety_rules:publish")),
    db: Session = Depends(get_db),
):
    try:
        return retire_safety_release(db, release_id, reviewer.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SafetyRuleConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
