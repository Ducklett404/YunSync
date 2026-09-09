from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.action import ActionOut
from app.services.action_service import action_service


router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("", response_model=list[ActionOut])
def list_actions(user_id: str = "demo-user", db: Session = Depends(get_db)):
    try:
        return action_service.ranked_actions(db, user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

