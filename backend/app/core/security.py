from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.identity import AuthSession
from app.models.user import UserProfile
from app.services.identity_service import hash_session_token, identity_service


ROLE_PERMISSIONS = {
    "participant": frozenset({"health:use", "profile:manage", "consent:manage"}),
    "reviewer": frozenset({"audit:read", "templates:manage", "safety_rules:publish"}),
}

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: UserProfile
    session: AuthSession


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def get_auth_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Session = Depends(get_db),
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录演示账号",
            headers={"WWW-Authenticate": "Bearer"},
        )
    statement = select(AuthSession).where(
        AuthSession.token_hash == hash_session_token(credentials.credentials)
    )
    session = db.scalar(statement)
    now = datetime.now(timezone.utc)
    if session is None or session.revoked_at is not None or _as_utc(session.expires_at) <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(UserProfile, session.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在")
    return AuthContext(user=user, session=session)


def get_current_user(context: AuthContext = Depends(get_auth_context)) -> UserProfile:
    return context.user


def require_permission(permission: str):
    def dependency(user: UserProfile = Depends(get_current_user)) -> UserProfile:
        if permission not in ROLE_PERMISSIONS.get(user.role, frozenset()):
            raise HTTPException(status_code=403, detail="当前角色无权执行此操作")
        return user

    return dependency


def require_active_participant(
    user: UserProfile = Depends(require_permission("health:use")),
    db: Session = Depends(get_db),
) -> UserProfile:
    if identity_service.active_consent(db, user.id) is None:
        raise HTTPException(status_code=403, detail="请先接受当前版本的知情说明")
    return user


def require_safe_participant(
    user: UserProfile = Depends(require_active_participant),
) -> UserProfile:
    if user.screening_status != "eligible" or user.high_risk:
        raise HTTPException(status_code=409, detail="请先完成安全初筛且不得触发高风险条件")
    return user
