import json

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_active_participant
from app.db.session import get_db
from app.models.user import UserProfile
from app.models.care_plan import CarePlan
from app.schemas.care_plan import (
    AdherenceLogIn, AdherenceLogOut, CarePlanOut, CarePlanRequest,
    PlanRevisionOut, ReminderIn, ReminderOut,
)
from app.services.care_plan_service import CarePlanConflict, care_plan_service
from app.services.care_plan_follow_up_service import (
    get_reminder, get_revision, list_logs, owned_plan, record_log, revise_plan, set_reminder,
)


router = APIRouter(prefix="/care-plans", tags=["care-plans"])


@router.get("/current", response_model=CarePlanOut | None)
def current_plan(
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    return care_plan_service.current(db, user)


@router.get("", response_model=list[CarePlanOut])
def plan_history(
    limit: int = Query(default=20, ge=1, le=100),
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    care_plan_service.current(db, user)
    return list(db.scalars(select(CarePlan).where(
        CarePlan.user_id == user.id,
    ).order_by(CarePlan.created_at.desc(), CarePlan.id.desc()).limit(limit)))


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


@router.get("/{plan_id}", response_model=CarePlanOut)
def get_plan(
    plan_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        plan = owned_plan(db, user, plan_id)
        return care_plan_service.refresh_status(db, user, plan)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{plan_id}/logs", response_model=list[AdherenceLogOut])
def get_logs(
    plan_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        return list_logs(db, user, plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{plan_id}/logs/{day}", response_model=AdherenceLogOut)
def put_log(
    plan_id: str,
    payload: AdherenceLogIn,
    day: int = Path(ge=1, le=7),
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        return record_log(db, user, plan_id, day, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CarePlanConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _reminder_out(reminder) -> ReminderOut:
    return ReminderOut(
        id=reminder.id, plan_id=reminder.plan_id, remind_on=reminder.remind_on,
        basis=reminder.basis, note=reminder.note, enabled=reminder.enabled,
        due=reminder.enabled and reminder.remind_on <= date.today(),
        updated_at=reminder.updated_at,
    )


@router.get("/{plan_id}/reminder", response_model=ReminderOut | None)
def read_reminder(
    plan_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        reminder = get_reminder(db, user, plan_id)
        return _reminder_out(reminder) if reminder else None
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{plan_id}/reminder", response_model=ReminderOut)
def put_reminder(
    plan_id: str,
    payload: ReminderIn,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        return _reminder_out(set_reminder(db, user, plan_id, payload))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CarePlanConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{plan_id}/revise", response_model=CarePlanOut, status_code=201)
def revise(
    plan_id: str,
    payload: CarePlanRequest,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        return revise_plan(db, user, plan_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CarePlanConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{plan_id}/revision", response_model=PlanRevisionOut | None)
def read_revision(
    plan_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        return get_revision(db, user, plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{plan_id}/export")
def export_plan(
    plan_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    plan = db.get(CarePlan, plan_id)
    if plan is None or plan.user_id != user.id:
        raise HTTPException(status_code=404, detail="方案不存在")
    plan = care_plan_service.refresh_status(db, user, plan)
    body = json.dumps({
        "format": "yunsync-care-plan-v2",
        "plan_id": plan.id,
        "version": plan.version,
        "previous_plan_id": plan.previous_plan_id,
        "status": plan.status,
        "pause_reason": plan.pause_reason,
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
