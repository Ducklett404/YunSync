from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.action import ActionTemplate
from app.models.audit import AuditLog
from app.repositories.action_repository import action_repository
from app.schemas.action import ActionTemplateStatusUpdate


class TemplateConflictError(RuntimeError):
    pass


class TemplateAdminService:
    def create_version(
        self,
        db: Session,
        source_id: str,
        version: str,
        reviewer_id: str,
    ) -> ActionTemplate:
        source = action_repository.get(db, source_id)
        if source is None:
            raise LookupError("行动模板不存在")
        if action_repository.version(db, source.code, version) is not None:
            raise TemplateConflictError("该行动代码的版本已存在")

        created = ActionTemplate(
            id=str(uuid4()),
            code=source.code,
            version=version,
            title=source.title,
            category=source.category,
            description=source.description,
            evidence_summary=source.evidence_summary,
            suitable_if=source.suitable_if,
            safety_note=source.safety_note,
            primary_metric=source.primary_metric,
            evidence_score=source.evidence_score,
            effort_score=source.effort_score,
            observability_score=source.observability_score,
            risk_level=source.risk_level,
            review_status="draft",
            review_scope="prototype_rules",
            is_active=False,
            contraindication_codes=list(source.contraindication_codes),
            signal_metric_codes=list(source.signal_metric_codes),
            ranking_policy_version=source.ranking_policy_version,
            explanation_policy_version=source.explanation_policy_version,
        )
        db.add(created)
        db.flush()
        db.add(
            AuditLog(
                event_type="action_template.version_created",
                actor_id=reviewer_id,
                payload={
                    "template_id": created.id,
                    "source_template_id": source.id,
                    "code": created.code,
                    "version": created.version,
                },
            )
        )
        db.commit()
        db.refresh(created)
        return created

    def update_status(
        self,
        db: Session,
        template_id: str,
        payload: ActionTemplateStatusUpdate,
        reviewer_id: str,
    ) -> ActionTemplate:
        template = action_repository.get(db, template_id)
        if template is None:
            raise LookupError("行动模板不存在")
        if payload.is_active and payload.review_status != "prototype_approved":
            raise TemplateConflictError("只有完成原型规则校验的模板才能在演示环境启用")
        if template.review_status == "retired" and payload.review_status != "retired":
            raise TemplateConflictError("已停用版本不可恢复，请创建新版本")

        now = datetime.now(timezone.utc)
        if payload.is_active:
            db.execute(
                update(ActionTemplate)
                .where(
                    ActionTemplate.code == template.code,
                    ActionTemplate.id != template.id,
                    ActionTemplate.is_active.is_(True),
                )
                .values(is_active=False, deactivated_at=now)
            )
        template.review_status = payload.review_status
        template.is_active = payload.is_active
        template.reviewer_ref = reviewer_id
        if payload.review_status == "prototype_approved":
            template.reviewed_at = now
        if not payload.is_active:
            template.deactivated_at = now
        else:
            template.deactivated_at = None

        db.add(
            AuditLog(
                event_type="action_template.status_changed",
                actor_id=reviewer_id,
                payload={
                    "template_id": template.id,
                    "code": template.code,
                    "version": template.version,
                    "review_status": template.review_status,
                    "is_active": template.is_active,
                },
            )
        )
        db.commit()
        db.refresh(template)
        return template


template_admin_service = TemplateAdminService()
