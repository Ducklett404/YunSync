from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    AuthContext,
    get_auth_context,
    get_current_user,
    require_active_participant,
    require_permission,
)
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.user import UserProfile
from app.schemas.food_safety import FoodSafetyProfileIn, FoodSafetyProfileOut
from app.schemas.common import ApiMessage
from app.schemas.identity import (
    AccountStatusOut,
    AuditEventOut,
    ConsentAcceptIn,
    ConsentNoticeOut,
    ConsentOut,
    DemoLoginIn,
    ProfileUpdateIn,
    SafetyScreeningIn,
    SessionOut,
    UserOut,
)
from app.services.identity_service import CURRENT_CONSENT_VERSION, identity_service
from app.services.food_safety_service import get_food_safety_profile, save_food_safety_profile


router = APIRouter()


@router.post("/auth/demo", response_model=SessionOut, tags=["auth"])
def demo_login(payload: DemoLoginIn, db: Session = Depends(get_db)):
    try:
        token, session, user = identity_service.issue_demo_session(db, payload.account_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return SessionOut(access_token=token, expires_at=session.expires_at, user=user)


@router.get("/auth/me", response_model=UserOut, tags=["auth"])
def auth_me(user: UserProfile = Depends(get_current_user)):
    return user


@router.post("/auth/logout", response_model=ApiMessage, tags=["auth"])
def logout(context: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    context.session.revoked_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(event_type="auth.logout", actor_id=context.user.id, payload={})
    )
    db.commit()
    return ApiMessage(message="已退出演示账号")


@router.get("/consents/notice", response_model=ConsentNoticeOut, tags=["consent"])
def consent_notice():
    return ConsentNoticeOut(
        version=CURRENT_CONSENT_VERSION,
        title="云循合成数据演示知情说明",
        items=[
            "用于合成体检报告核对和食养安全档案演示；食养方案尚未开放，不提供诊断、治疗、处方或调药建议。",
            "当前开发版本只允许使用合成或已脱敏材料，不应填写真实身份、疾病、过敏或用药信息。",
            "可以随时撤回授权；撤回后停止新的健康数据操作，暂停进行中的照护方案和历史实验，并保留导出与删除入口。",
        ],
    )


@router.get("/account/status", response_model=AccountStatusOut, tags=["account"])
def account_status(
    user: UserProfile = Depends(get_current_user), db: Session = Depends(get_db)
):
    return AccountStatusOut(
        user=user,
        consent=identity_service.active_consent(db, user.id),
        required_consent_version=CURRENT_CONSENT_VERSION,
    )


@router.post("/consents/accept", response_model=ConsentOut, tags=["consent"])
def accept_consent(
    payload: ConsentAcceptIn,
    user: UserProfile = Depends(require_permission("consent:manage")),
    db: Session = Depends(get_db),
):
    try:
        return identity_service.accept_consent(db, user.id, payload.version)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/consents/withdraw", response_model=ApiMessage, tags=["consent"])
def withdraw_consent(
    user: UserProfile = Depends(require_permission("consent:manage")),
    db: Session = Depends(get_db),
):
    withdrawn = identity_service.withdraw_consent(db, user.id)
    return ApiMessage(message="授权已撤回" if withdrawn else "当前没有生效中的授权")


@router.get("/profile", response_model=UserOut, tags=["profile"])
def get_profile(user: UserProfile = Depends(require_active_participant)):
    return user


@router.patch("/profile", response_model=UserOut, tags=["profile"])
def update_profile(
    payload: ProfileUpdateIn,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    return identity_service.update_profile(db, user, payload)


@router.get("/profile/food-safety", response_model=FoodSafetyProfileOut, tags=["profile"])
def read_food_safety_profile(
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    return get_food_safety_profile(db, user)


@router.patch("/profile/food-safety", response_model=FoodSafetyProfileOut, tags=["profile"])
def update_food_safety_profile(
    payload: FoodSafetyProfileIn,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    return save_food_safety_profile(db, user, payload)


@router.post("/profile/screening", response_model=UserOut, tags=["profile"])
def save_screening(
    payload: SafetyScreeningIn,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    return identity_service.save_screening(db, user, payload)


@router.get("/admin/audit-events", response_model=list[AuditEventOut], tags=["admin"])
def list_audit_events(
    _user: UserProfile = Depends(require_permission("audit:read")),
    db: Session = Depends(get_db),
):
    statement = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100)
    return list(db.scalars(statement))
