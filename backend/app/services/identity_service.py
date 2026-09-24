import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit import AuditLog
from app.models.care_plan import CarePlan
from app.models.experiment import Experiment
from app.models.identity import AuthSession, ConsentRecord
from app.models.privacy import PrivacyRequest
from app.models.user import UserProfile
from app.schemas.identity import ProfileUpdateIn, SafetyScreeningIn


CURRENT_CONSENT_VERSION = "2026-09-20.v2"
DEMO_ACCOUNT_USERS = {
    "demo-student": "demo-user",
    "demo-reviewer": "demo-reviewer",
}


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class IdentityService:
    def issue_demo_session(self, db: Session, account_id: str) -> tuple[str, AuthSession, UserProfile]:
        if not settings.enable_demo_login:
            raise PermissionError("演示账号登录已关闭")
        user_id = DEMO_ACCOUNT_USERS.get(account_id)
        user = db.get(UserProfile, user_id) if user_id else None
        if user is None:
            raise LookupError("演示账号不存在")

        token = secrets.token_urlsafe(32)
        session = AuthSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours),
        )
        db.add(session)
        db.add(
            AuditLog(
                event_type="auth.demo_login",
                actor_id=user.id,
                payload={"role": user.role},
            )
        )
        db.commit()
        db.refresh(session)
        return token, session, user

    def active_consent(self, db: Session, user_id: str) -> ConsentRecord | None:
        statement = (
            select(ConsentRecord)
            .where(
                ConsentRecord.user_id == user_id,
                ConsentRecord.status == "active",
                ConsentRecord.version == CURRENT_CONSENT_VERSION,
            )
            .order_by(ConsentRecord.accepted_at.desc())
            .limit(1)
        )
        return db.scalar(statement)

    def accept_consent(self, db: Session, user_id: str, version: str) -> ConsentRecord:
        if version != CURRENT_CONSENT_VERSION:
            raise ValueError("授权版本已更新，请重新阅读当前说明")
        pending_deletion = db.scalar(
            select(PrivacyRequest.id).where(
                PrivacyRequest.user_id == user_id,
                PrivacyRequest.request_type == "account_deletion",
                PrivacyRequest.status == "pending",
            )
        )
        if pending_deletion is not None:
            raise ValueError("账号删除请求待执行，请先取消删除请求再重新授权")
        active = self.active_consent(db, user_id)
        if active is not None:
            return active

        now = datetime.now(timezone.utc)
        db.execute(
            update(ConsentRecord)
            .where(ConsentRecord.user_id == user_id, ConsentRecord.status == "active")
            .values(status="withdrawn", withdrawn_at=now)
        )
        consent = ConsentRecord(user_id=user_id, version=version, status="active")
        db.add(consent)
        db.add(
            AuditLog(
                event_type="consent.accepted",
                actor_id=user_id,
                payload={"version": version},
            )
        )
        db.commit()
        db.refresh(consent)
        return consent

    def withdraw_consent(self, db: Session, user_id: str, *, commit: bool = True) -> bool:
        active = self.active_consent(db, user_id)
        if active is None:
            return False
        active.status = "withdrawn"
        active.withdrawn_at = datetime.now(timezone.utc)
        paused_count = self._pause_active_experiments(
            db, user_id, reason="consent_withdrawn"
        )
        paused_plan_count = self._pause_active_care_plans(
            db, user_id, reason="consent_withdrawn"
        )
        db.add(
            AuditLog(
                event_type="consent.withdrawn",
                actor_id=user_id,
                payload={
                    "version": active.version,
                    "active_experiments_paused": paused_count,
                    "active_care_plans_paused": paused_plan_count,
                },
            )
        )
        if commit:
            db.commit()
        return True

    def update_profile(
        self, db: Session, user: UserProfile, payload: ProfileUpdateIn
    ) -> UserProfile:
        changes = payload.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(user, field, value)
        db.add(
            AuditLog(
                event_type="profile.updated",
                actor_id=user.id,
                payload={"changed_fields": sorted(changes)},
            )
        )
        db.commit()
        db.refresh(user)
        return user

    def save_screening(
        self, db: Session, user: UserProfile, payload: SafetyScreeningIn
    ) -> UserProfile:
        answers = payload.model_dump()
        triggered_count = sum(answers.values())
        user.screening_answers = answers
        user.high_risk = triggered_count > 0
        user.screening_status = (
            "needs_professional_review" if user.high_risk else "eligible"
        )
        user.screened_at = datetime.now(timezone.utc)
        if user.high_risk:
            self._pause_active_experiments(
                db, user.id, reason="safety_screening_triggered"
            )
        db.add(
            AuditLog(
                event_type="safety.screening_saved",
                actor_id=user.id,
                payload={"status": user.screening_status, "triggered_count": triggered_count},
            )
        )
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def _pause_active_experiments(db: Session, user_id: str, reason: str) -> int:
        experiments = list(
            db.scalars(
                select(Experiment).where(
                    Experiment.user_id == user_id,
                    Experiment.status == "active",
                )
            )
        )
        now = datetime.now(timezone.utc)
        for experiment in experiments:
            experiment.status = "paused"
            experiment.paused_at = now
            experiment.updated_at = now
            db.add(
                AuditLog(
                    event_type="experiment.paused",
                    actor_id=user_id,
                    payload={
                        "experiment_id": experiment.id,
                        "from_status": "active",
                        "to_status": "paused",
                        "reason": reason,
                    },
                )
            )
        return len(experiments)

    @staticmethod
    def _pause_active_care_plans(db: Session, user_id: str, reason: str) -> int:
        plans = list(
            db.scalars(
                select(CarePlan).where(
                    CarePlan.user_id == user_id,
                    CarePlan.status == "ACTIVE",
                )
            )
        )
        now = datetime.now(timezone.utc)
        for plan in plans:
            plan.status = "PAUSED"
            plan.paused_at = now
            plan.pause_reason = reason
            db.add(
                AuditLog(
                    event_type="care_plan.paused",
                    actor_id=user_id,
                    payload={"plan_id": plan.id, "reason": reason},
                )
            )
        return len(plans)


identity_service = IdentityService()
