import json

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.security import require_active_participant
from app.db.session import get_db
from app.models.user import UserProfile
from app.models.care_plan import CarePlan
from app.schemas.care_plan import CarePlanOut, CarePlanRequest
from app.services.care_plan_service import CarePlanConflict, care_plan_service


router = APIRouter(prefix="/care-plans", tags=["care-plans"])


@router.get("/current", response_model=CarePlanOut | None)
def current_plan(
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    return care_plan_service.current(db, user)


@router.post("", response_model=CarePlanOut, status_code=201)
def create_plan(
    payload: CarePlanRequest,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        return care_plan_service.create(db, user, payload)
    except CarePlanConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{plan_id}/activate", response_model=CarePlanOut)
def activate_plan(
    plan_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        return care_plan_service.activate(db, user, plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CarePlanConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{plan_id}/export")
def export_plan(
    plan_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    plan = db.get(CarePlan, plan_id)
    if plan is None or plan.user_id != user.id:
        raise HTTPException(status_code=404, detail="方案不存在")
    if plan.status == "ACTIVE":
        care_plan_service.current(db, user)
        db.refresh(plan)
    body = json.dumps({
        "format": "yunsync-care-plan-v1",
        "status": plan.status,
        "created_at": plan.created_at.isoformat(),
        "snapshot": plan.snapshot,
    }, ensure_ascii=False).encode("utf-8")
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'attachment; filename="yunsync-care-plan-{plan.id}.json"',
        },
    )
