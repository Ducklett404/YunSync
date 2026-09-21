from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.food_safety import SafetyRuleRelease
from app.schemas.safety_decision import SafetyRuleReleaseIn


REQUIRED_SAFETY_RULE_CODES = frozenset(
    {
        "acute_symptoms",
        "report_critical_marker",
        "allergy_status",
        "medication_status",
        "condition_status",
        "liver_kidney_status",
        "clinician_restriction_status",
        "special_status",
        "missing_information",
    }
)


class SafetyRuleConflictError(RuntimeError):
    pass


def active_safety_release(db: Session) -> SafetyRuleRelease | None:
    return db.scalar(
        select(SafetyRuleRelease)
        .where(SafetyRuleRelease.status == "published")
        .order_by(SafetyRuleRelease.published_at.desc())
        .limit(1)
    )


def list_safety_releases(db: Session) -> list[SafetyRuleRelease]:
    return list(
        db.scalars(
            select(SafetyRuleRelease).order_by(
                SafetyRuleRelease.published_at.desc(), SafetyRuleRelease.id.desc()
            )
        )
    )


def publish_safety_release(
    db: Session, payload: SafetyRuleReleaseIn, reviewer_id: str
) -> SafetyRuleRelease:
    existing = db.scalar(
        select(SafetyRuleRelease).where(SafetyRuleRelease.version == payload.version)
    )
    if existing is not None:
        raise SafetyRuleConflictError("该安全规则版本已存在")
    missing = REQUIRED_SAFETY_RULE_CODES.difference(payload.reviewed_rule_codes)
    if missing:
        raise SafetyRuleConflictError(f"审核范围不完整，缺少：{', '.join(sorted(missing))}")

    now = datetime.now(timezone.utc)
    current = active_safety_release(db)
    if current is not None:
        current.status = "retired"
        current.retired_at = now
    release = SafetyRuleRelease(
        id=str(uuid4()),
        version=payload.version,
        status="published",
        evidence_ref=payload.evidence_ref,
        reviewer_qualification=payload.reviewer_qualification,
        reviewed_rule_codes=payload.reviewed_rule_codes,
        attested=payload.attested,
        reviewer_id=reviewer_id,
        published_at=now,
    )
    db.add(release)
    db.add(
        AuditLog(
            event_type="safety_rule_release.published",
            actor_id=reviewer_id,
            payload={
                "release_id": release.id,
                "version": release.version,
                "reviewed_rule_codes": release.reviewed_rule_codes,
                "superseded_release_id": current.id if current else None,
            },
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SafetyRuleConflictError("安全规则版本或活动发布状态发生冲突，请刷新后重试") from exc
    db.refresh(release)
    return release


def retire_safety_release(
    db: Session, release_id: str, reviewer_id: str
) -> SafetyRuleRelease:
    release = db.get(SafetyRuleRelease, release_id)
    if release is None:
        raise LookupError("安全规则版本不存在")
    if release.status != "published":
        raise SafetyRuleConflictError("该安全规则版本已停用")
    release.status = "retired"
    release.retired_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            event_type="safety_rule_release.retired",
            actor_id=reviewer_id,
            payload={"release_id": release.id, "version": release.version},
        )
    )
    db.commit()
    db.refresh(release)
    return release
