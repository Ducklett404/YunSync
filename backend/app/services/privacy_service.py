from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import hmac
from typing import Any

from sqlalchemy import delete, inspect, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.huawei.obs import (
    HuaweiObsClient,
    LocalPrivateStorageClient,
    ObjectStorageError,
)
from app.models.audit import AuditLog
from app.models.care_plan import AdherenceLog, CarePlan, FollowUpReminder, PlanRevision
from app.models.experiment import Experiment, Observation
from app.models.food_safety import FoodSafetyProfile
from app.models.health import HealthMetric, HealthReport
from app.models.identity import AuthSession, ConsentRecord
from app.models.privacy import PrivacyRequest
from app.models.user import UserProfile
from app.services.identity_service import identity_service


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _record(model: Any, *, exclude: set[str] | None = None) -> dict[str, Any]:
    blocked = exclude or set()
    return {
        column.key: _json_value(getattr(model, column.key))
        for column in inspect(model).mapper.column_attrs
        if column.key not in blocked
    }


class PrivacyService:
    @staticmethod
    def subject_hash(user_id: str) -> str:
        return hmac.new(
            settings.secret_key.encode(),
            f"yunsync-privacy-subject-v1:{user_id}".encode(),
            sha256,
        ).hexdigest()

    def pending_request(self, db: Session, user_id: str) -> PrivacyRequest | None:
        return db.scalar(
            select(PrivacyRequest)
            .where(
                PrivacyRequest.user_id == user_id,
                PrivacyRequest.request_type == "account_deletion",
                PrivacyRequest.status == "pending",
            )
            .order_by(PrivacyRequest.requested_at.desc())
            .limit(1)
        )

    def export_account(self, db: Session, user: UserProfile) -> dict[str, Any]:
        reports = list(db.scalars(select(HealthReport).where(HealthReport.user_id == user.id)))
        report_ids = [item.id for item in reports]
        experiments = list(db.scalars(select(Experiment).where(Experiment.user_id == user.id)))
        experiment_ids = [item.id for item in experiments]

        def rows(model: Any, condition: Any) -> list[dict[str, Any]]:
            return [_record(item) for item in db.scalars(select(model).where(condition))]

        return {
            "format": "yunsync-account-export-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "notice": "此导出包含账号当前保存的数据。报告源文件需在报告页单独下载。",
            "profile": _record(user),
            "consents": rows(ConsentRecord, ConsentRecord.user_id == user.id),
            "reports": [
                _record(item, exclude={"storage_key", "content_sha256"}) for item in reports
            ],
            "metrics": (
                rows(HealthMetric, HealthMetric.report_id.in_(report_ids)) if report_ids else []
            ),
            "food_safety_profile": (
                _record(profile)
                if (profile := db.get(FoodSafetyProfile, user.id)) is not None
                else None
            ),
            "care_plans": rows(CarePlan, CarePlan.user_id == user.id),
            "adherence_logs": rows(AdherenceLog, AdherenceLog.user_id == user.id),
            "follow_up_reminders": rows(
                FollowUpReminder, FollowUpReminder.user_id == user.id
            ),
            "plan_revisions": rows(PlanRevision, PlanRevision.user_id == user.id),
            "experiments": [_record(item) for item in experiments],
            "observations": (
                rows(Observation, Observation.experiment_id.in_(experiment_ids))
                if experiment_ids
                else []
            ),
            "audit_events": rows(AuditLog, AuditLog.actor_id == user.id),
        }

    def request_account_deletion(self, db: Session, user_id: str) -> PrivacyRequest:
        existing = self.pending_request(db, user_id)
        if existing is not None:
            return existing
        withdrawn = identity_service.withdraw_consent(db, user_id, commit=False)
        if not withdrawn:
            identity_service._pause_active_experiments(
                db, user_id, reason="account_deletion_requested"
            )
            identity_service._pause_active_care_plans(
                db, user_id, reason="account_deletion_requested"
            )
        now = datetime.now(timezone.utc)
        request = PrivacyRequest(
            user_id=user_id,
            subject_hash=self.subject_hash(user_id),
            request_type="account_deletion",
            status="pending",
            requested_at=now,
            execute_after=now + timedelta(hours=settings.account_deletion_grace_hours),
        )
        db.add(request)
        db.flush()
        db.add(
            AuditLog(
                event_type="privacy.account_deletion_requested",
                actor_id=user_id,
                payload={"request_id": request.id, "grace_hours": settings.account_deletion_grace_hours},
            )
        )
        db.commit()
        db.refresh(request)
        return request

    def cancel_account_deletion(self, db: Session, user_id: str) -> PrivacyRequest:
        request = self.pending_request(db, user_id)
        if request is None:
            raise LookupError("没有待执行的账号删除请求")
        request.status = "cancelled"
        request.cancelled_at = datetime.now(timezone.utc)
        db.add(
            AuditLog(
                event_type="privacy.account_deletion_cancelled",
                actor_id=user_id,
                payload={"request_id": request.id},
            )
        )
        db.commit()
        db.refresh(request)
        return request

    @staticmethod
    def _storage(report: HealthReport):
        if report.storage_provider == "huawei_obs":
            return HuaweiObsClient()
        if report.storage_provider == "local_private":
            return LocalPrivateStorageClient()
        raise ObjectStorageError("报告使用了不受支持的私有存储提供方")

    def delete_report(self, db: Session, user_id: str, report_id: str) -> None:
        report = db.scalar(
            select(HealthReport).where(
                HealthReport.id == report_id, HealthReport.user_id == user_id
            )
        )
        if report is None:
            raise LookupError("报告不存在或不属于当前用户")
        if report.storage_key:
            self._storage(report).delete_private(report.storage_key)
        provider = report.storage_provider
        db.delete(report)
        db.add(
            AuditLog(
                event_type="privacy.report_deleted",
                actor_id=user_id,
                payload={"report_id": report_id, "storage_provider": provider},
            )
        )
        db.commit()

    def process_due_deletions(
        self, db: Session, *, now: datetime | None = None, dry_run: bool = False
    ) -> dict[str, int]:
        current = now or datetime.now(timezone.utc)
        requests = list(
            db.scalars(
                select(PrivacyRequest).where(
                    PrivacyRequest.status == "pending",
                    PrivacyRequest.execute_after <= current,
                )
            )
        )
        result = {"due": len(requests), "completed": 0, "failed": 0}
        if dry_run:
            return result
        for request in requests:
            if not request.user_id or db.get(UserProfile, request.user_id) is None:
                request.user_id = None
                request.status = "completed"
                request.completed_at = current
                request.last_error_code = None
                result["completed"] += 1
                continue
            try:
                reports = list(
                    db.scalars(select(HealthReport).where(HealthReport.user_id == request.user_id))
                )
                for report in reports:
                    if report.storage_key:
                        self._storage(report).delete_private(report.storage_key)
            except ObjectStorageError:
                request.attempt_count += 1
                request.last_error_code = "object_storage_delete_failed"
                result["failed"] += 1
                db.commit()
                continue

            user_id = request.user_id
            subject = request.subject_hash
            db.execute(
                update(AuditLog)
                .where(AuditLog.actor_id == user_id)
                .values(actor_id=f"privacy-{subject[:28]}", payload={"redacted": True})
            )
            user = db.get(UserProfile, user_id)
            if user is not None:
                db.delete(user)
                db.flush()
            request.user_id = None
            request.status = "completed"
            request.completed_at = current
            request.last_error_code = None
            db.add(
                AuditLog(
                    event_type="privacy.account_deletion_completed",
                    actor_id="system",
                    payload={"request_id": request.id},
                )
            )
            db.commit()
            result["completed"] += 1
        db.commit()
        return result

    @staticmethod
    def purge_expired_sessions(
        db: Session, *, now: datetime | None = None, dry_run: bool = False
    ) -> int:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(
            days=settings.expired_session_retention_days
        )
        condition = (AuthSession.expires_at < cutoff) | (
            AuthSession.revoked_at.is_not(None) & (AuthSession.revoked_at < cutoff)
        )
        sessions = list(db.scalars(select(AuthSession.id).where(condition)))
        if not dry_run and sessions:
            db.execute(delete(AuthSession).where(AuthSession.id.in_(sessions)))
            db.commit()
        return len(sessions)


privacy_service = PrivacyService()
