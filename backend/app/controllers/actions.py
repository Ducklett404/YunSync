from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_safe_participant
from app.db.session import get_db
from app.models.user import UserProfile
from app.schemas.action import ActionOut
from app.services.action_service import action_service


router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("", response_model=list[ActionOut])
async def list_actions(
    user: UserProfile = Depends(require_safe_participant),
    db: Session = Depends(get_db),
):
    try:
        return await action_service.ranked_actions(db, user.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
