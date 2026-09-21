from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.content import ContentReview, EvidenceSource, KnowledgeItem
from app.schemas.content import (
    BulkValidationOut,
    ContentCompareOut,
    ContentItemCreate,
    ContentReviewIn,
    ContentValidationResult,
    EvidenceSourceIn,
    IngredientPayload,
    RecipePayload,
    ContraindicationPayload,
    parse_content_payload,
)


PROHIBITED_MEDICAL_CLAIMS = (
    "治疗",
    "治愈",
    "降血糖",
    "降血压",
    "降血脂",
    "排毒",
    "逆转疾病",
    "替代药物",
    "停止用药",
    "停药",
    "疗效",
)


class ContentConflictError(RuntimeError):
    pass


def _audit(db: Session, event_type: str, actor_id: str, item: KnowledgeItem, **extra) -> None:
    payload = {
        "item_id": item.id,
        "content_type": item.content_type,
        "code": item.code,
        "version": item.version,
        "status": item.status,
    }
    payload.update(extra)
    db.add(AuditLog(event_type=event_type, actor_id=actor_id, payload=payload))


def _source_refs(payload: IngredientPayload | RecipePayload | ContraindicationPayload) -> list[str]:
    return list(payload.source_refs)


def _claim_matches(title: str, payload: dict) -> list[str]:
    searchable = f"{title}\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    return [claim for claim in PROHIBITED_MEDICAL_CLAIMS if claim in searchable]


def _flatten(value: object, prefix: str = "") -> dict[str, object | None]:
    if isinstance(value, dict):
        result: dict[str, object | None] = {}
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten(value[key], path))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            result.update(_flatten(item, f"{prefix}[{index}]"))
        if not value:
            result[prefix] = []
        return result
    return {prefix: value}


class ContentService:
    def list_sources(
        self, db: Session, q: str = "", status: str | None = None
    ) -> list[EvidenceSource]:
        statement = select(EvidenceSource)
        if status:
            statement = statement.where(EvidenceSource.status == status)
        if q.strip():
            pattern = f"%{q.strip()}%"
            statement = statement.where(
                or_(
                    EvidenceSource.title.ilike(pattern),
                    EvidenceSource.code.ilike(pattern),
                    EvidenceSource.publisher.ilike(pattern),
                )
            )
        return list(db.scalars(statement.order_by(EvidenceSource.created_at.desc())))

    def create_source(
        self, db: Session, payload: EvidenceSourceIn, actor_id: str
    ) -> EvidenceSource:
        existing = db.scalar(
            select(EvidenceSource).where(
                EvidenceSource.code == payload.code,
                EvidenceSource.version == payload.version,
            )
        )
        if existing is not None:
            raise ContentConflictError("该来源版本已存在")
        source = EvidenceSource(id=str(uuid4()), **payload.model_dump())
        db.add(source)
        db.add(
            AuditLog(
                event_type="content.source.created",
                actor_id=actor_id,
                payload={"source_id": source.id, "ref": source.ref, "status": source.status},
            )
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ContentConflictError("该来源版本已存在") from exc
        db.refresh(source)
        return source

    def update_source_status(
        self, db: Session, source_id: str, status: str, actor_id: str
    ) -> EvidenceSource:
        source = db.get(EvidenceSource, source_id)
        if source is None:
            raise LookupError("证据来源不存在")
        if status != "active":
            active_items = list(
                db.scalars(
                    select(KnowledgeItem).where(
                        KnowledgeItem.status == "published",
                        KnowledgeItem.is_active.is_(True),
                    )
                )
            )
            blockers = [
                f"{item.content_type}:{item.code}@{item.version}"
                for item in active_items
                if source.ref in item.payload.get("source_refs", [])
            ]
            if blockers:
                raise ContentConflictError(
                    f"来源仍被已发布内容引用，请先停用内容：{', '.join(blockers[:5])}"
                )
        source.status = status
        db.add(
            AuditLog(
                event_type="content.source.status_changed",
                actor_id=actor_id,
                payload={"source_id": source.id, "ref": source.ref, "status": status},
            )
        )
        db.commit()
        db.refresh(source)
        return source

    def list_items(
        self,
        db: Session,
        content_type: str | None = None,
        status: str | None = None,
        q: str = "",
    ) -> list[KnowledgeItem]:
        statement = select(KnowledgeItem)
        if content_type:
            statement = statement.where(KnowledgeItem.content_type == content_type)
        if status:
            statement = statement.where(KnowledgeItem.status == status)
        if q.strip():
            pattern = f"%{q.strip()}%"
            statement = statement.where(
                or_(KnowledgeItem.title.ilike(pattern), KnowledgeItem.code.ilike(pattern))
            )
        return list(
            db.scalars(
                statement.order_by(
                    KnowledgeItem.content_type,
                    KnowledgeItem.code,
                    KnowledgeItem.created_at.desc(),
                )
            )
        )

    def create_item(
        self, db: Session, payload: ContentItemCreate, actor_id: str
    ) -> KnowledgeItem:
        matches = _claim_matches(payload.title, payload.payload)
        if matches:
            raise ContentConflictError(f"内容包含禁止的医疗功效表述：{', '.join(matches)}")
        existing = db.scalar(
            select(KnowledgeItem).where(
                KnowledgeItem.content_type == payload.content_type,
                KnowledgeItem.code == payload.code,
                KnowledgeItem.version == payload.version,
            )
        )
        if existing is not None:
            raise ContentConflictError("该内容版本已存在")
        item = KnowledgeItem(
            id=str(uuid4()),
            **payload.model_dump(),
            status="draft",
            is_active=False,
            created_by=actor_id,
        )
        db.add(item)
        _audit(db, "content.item.created", actor_id, item)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ContentConflictError("该内容版本已存在") from exc
        db.refresh(item)
        return item

    @staticmethod
    def latest_review(db: Session, item_id: str) -> ContentReview | None:
        return db.scalar(
            select(ContentReview)
            .where(ContentReview.item_id == item_id)
            .order_by(ContentReview.created_at.desc(), ContentReview.id.desc())
            .limit(1)
        )

    def review_item(
        self,
        db: Session,
        item_id: str,
        payload: ContentReviewIn,
        reviewer_id: str,
    ) -> ContentReview:
        item = db.get(KnowledgeItem, item_id)
        if item is None:
            raise LookupError("知识条目不存在")
        if item.status in {"published", "retired"}:
            raise ContentConflictError("已发布或已停用版本不能追加审核，请创建新版本")
        review = ContentReview(
            id=str(uuid4()),
            item_id=item.id,
            decision=payload.decision,
            reviewer_id=reviewer_id,
            reviewer_qualification=payload.reviewer_qualification,
            review_scope=payload.review_scope,
            evidence_ref=payload.evidence_ref,
            attested=payload.attested,
            notes=payload.notes,
        )
        item.status = "reviewed" if payload.decision == "approved" else "draft"
        db.add(review)
        _audit(
            db,
            "content.item.reviewed",
            reviewer_id,
            item,
            decision=payload.decision,
            review_id=review.id,
        )
        db.commit()
        db.refresh(review)
        return review

    def validate_item(self, db: Session, item: KnowledgeItem) -> ContentValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        try:
            payload = parse_content_payload(item.content_type, item.payload)
        except (KeyError, ValueError) as exc:
            return ContentValidationResult(
                item_id=item.id,
                content_type=item.content_type if item.content_type in {"ingredient", "recipe", "contraindication"} else None,
                code=item.code,
                version=item.version,
                valid=False,
                errors=[f"结构校验失败：{exc}"],
                warnings=[],
            )

        matches = _claim_matches(item.title, item.payload)
        if matches:
            errors.append(f"包含禁止的医疗功效表述：{', '.join(matches)}")

        sources = {
            source.ref: source
            for source in db.scalars(select(EvidenceSource)).all()
        }
        for ref in _source_refs(payload):
            source = sources.get(ref)
            if source is None:
                errors.append(f"证据来源不存在：{ref}")
            elif source.status != "active":
                errors.append(f"证据来源未生效：{ref}")

        if isinstance(payload, IngredientPayload):
            if payload.category == "food_medicine" and payload.catalog_status != "listed":
                errors.append("食药物质必须确认在目录中后才能发布")
            self._validate_contraindications(db, payload.contraindication_codes, errors)
        elif isinstance(payload, RecipePayload):
            material_refs = [
                (material.code, material.version)
                for material in payload.materials
            ]
            material_refs.extend(
                (sub.code, sub.version)
                for material in payload.materials
                for sub in material.substitutions
            )
            for code, version in material_refs:
                dependency = db.scalar(
                    select(KnowledgeItem).where(
                        KnowledgeItem.content_type == "ingredient",
                        KnowledgeItem.code == code,
                        KnowledgeItem.version == version,
                    )
                )
                if dependency is None:
                    errors.append(f"食材版本不存在：{code}@{version}")
                elif dependency.status != "published" or not dependency.is_active:
                    errors.append(f"食材版本尚未发布：{code}@{version}")
            self._validate_contraindications(db, payload.contraindication_codes, errors)
        elif isinstance(payload, ContraindicationPayload):
            subject = db.scalar(
                select(KnowledgeItem).where(
                    KnowledgeItem.content_type == payload.subject_type,
                    KnowledgeItem.code == payload.subject_code,
                )
            )
            if subject is None:
                errors.append(
                    f"适用对象不存在：{payload.subject_type}:{payload.subject_code}"
                )

        review = self.latest_review(db, item.id)
        if review is None or review.decision != "approved" or not review.attested:
            warnings.append("尚无最新的具名批准审核，不能发布")
        return ContentValidationResult(
            item_id=item.id,
            content_type=item.content_type,
            code=item.code,
            version=item.version,
            valid=not errors and not warnings,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _validate_contraindications(
        db: Session, codes: list[str], errors: list[str]
    ) -> None:
        for code in codes:
            dependency = db.scalar(
                select(KnowledgeItem).where(
                    KnowledgeItem.content_type == "contraindication",
                    KnowledgeItem.code == code,
                    KnowledgeItem.status == "published",
                    KnowledgeItem.is_active.is_(True),
                )
            )
            if dependency is None:
                errors.append(f"禁忌规则尚未发布：{code}")

    def bulk_validate(self, db: Session, item_ids: list[str]) -> BulkValidationOut:
        results: list[ContentValidationResult] = []
        for item_id in item_ids:
            item = db.get(KnowledgeItem, item_id)
            if item is None:
                results.append(
                    ContentValidationResult(
                        item_id=item_id,
                        content_type=None,
                        code=None,
                        version=None,
                        valid=False,
                        errors=["知识条目不存在"],
                        warnings=[],
                    )
                )
            else:
                results.append(self.validate_item(db, item))
        return BulkValidationOut(valid=all(result.valid for result in results), results=results)

    def publish_item(self, db: Session, item_id: str, actor_id: str) -> KnowledgeItem:
        item = db.get(KnowledgeItem, item_id)
        if item is None:
            raise LookupError("知识条目不存在")
        if item.status != "reviewed":
            raise ContentConflictError("只有已批准审核的版本才能发布")
        review = self.latest_review(db, item.id)
        if review is None or review.decision != "approved" or not review.attested:
            raise ContentConflictError("缺少最新的具名批准审核")
        validation = self.validate_item(db, item)
        if not validation.valid:
            raise ContentConflictError("发布校验失败：" + "；".join(validation.errors))

        now = datetime.now(timezone.utc)
        current = db.scalar(
            select(KnowledgeItem).where(
                KnowledgeItem.content_type == item.content_type,
                KnowledgeItem.code == item.code,
                KnowledgeItem.is_active.is_(True),
                KnowledgeItem.id != item.id,
            )
        )
        if current is not None:
            blockers = self._active_dependents(db, current)
            if blockers:
                raise ContentConflictError(
                    "旧版本仍被已发布内容精确引用，请先停用或升级依赖项："
                    + "、".join(blockers[:5])
                )
            current.status = "retired"
            current.is_active = False
            current.retired_at = now
            db.flush()
        item.status = "published"
        item.is_active = True
        item.published_at = now
        item.retired_at = None
        _audit(db, "content.item.published", actor_id, item)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ContentConflictError("同一内容只能有一个生效版本") from exc
        db.refresh(item)
        return item

    def retire_item(self, db: Session, item_id: str, actor_id: str) -> KnowledgeItem:
        item = db.get(KnowledgeItem, item_id)
        if item is None:
            raise LookupError("知识条目不存在")
        if item.status == "retired":
            raise ContentConflictError("该版本已经停用")
        blockers = self._active_dependents(db, item)
        if blockers:
            raise ContentConflictError(
                "该版本仍被已发布内容引用，请先停用依赖项："
                + "、".join(blockers[:5])
            )
        item.status = "retired"
        item.is_active = False
        item.retired_at = datetime.now(timezone.utc)
        _audit(db, "content.item.retired", actor_id, item)
        db.commit()
        db.refresh(item)
        return item

    def rollback_item(self, db: Session, item_id: str, actor_id: str) -> KnowledgeItem:
        target = db.get(KnowledgeItem, item_id)
        if target is None:
            raise LookupError("知识条目不存在")
        if target.status != "retired":
            raise ContentConflictError("只能回滚到已停用的历史版本")
        review = self.latest_review(db, target.id)
        if review is None or review.decision != "approved" or not review.attested:
            raise ContentConflictError("历史版本缺少可核验的批准审核")
        validation = self.validate_item(db, target)
        if not validation.valid:
            raise ContentConflictError("回滚校验失败：" + "；".join(validation.errors))

        now = datetime.now(timezone.utc)
        current = db.scalar(
            select(KnowledgeItem).where(
                KnowledgeItem.content_type == target.content_type,
                KnowledgeItem.code == target.code,
                KnowledgeItem.is_active.is_(True),
            )
        )
        replaced_id = None
        if current is not None:
            blockers = self._active_dependents(db, current)
            if blockers:
                raise ContentConflictError(
                    "当前版本仍被已发布内容引用，请先停用或升级依赖项："
                    + "、".join(blockers[:5])
                )
            replaced_id = current.id
            current.status = "retired"
            current.is_active = False
            current.retired_at = now
            db.flush()
        target.status = "published"
        target.is_active = True
        target.published_at = now
        target.retired_at = None
        _audit(
            db,
            "content.item.rolled_back",
            actor_id,
            target,
            replaced_item_id=replaced_id,
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ContentConflictError("回滚时检测到生效版本冲突") from exc
        db.refresh(target)
        return target

    @staticmethod
    def _active_dependents(db: Session, item: KnowledgeItem) -> list[str]:
        active_items = list(
            db.scalars(
                select(KnowledgeItem).where(
                    KnowledgeItem.status == "published",
                    KnowledgeItem.is_active.is_(True),
                    KnowledgeItem.id != item.id,
                )
            )
        )
        blockers: list[str] = []
        for candidate in active_items:
            payload = candidate.payload
            referenced = False
            if item.content_type == "ingredient" and candidate.content_type == "recipe":
                refs = [
                    (material.get("code"), material.get("version"))
                    for material in payload.get("materials", [])
                ]
                refs.extend(
                    (sub.get("code"), sub.get("version"))
                    for material in payload.get("materials", [])
                    for sub in material.get("substitutions", [])
                )
                referenced = (item.code, item.version) in refs
            elif item.content_type == "contraindication":
                referenced = item.code in payload.get("contraindication_codes", [])
            elif candidate.content_type == "contraindication":
                referenced = (
                    payload.get("subject_type") == item.content_type
                    and payload.get("subject_code") == item.code
                )
            if referenced:
                blockers.append(
                    f"{candidate.content_type}:{candidate.code}@{candidate.version}"
                )
        return blockers

    def compare_versions(
        self,
        db: Session,
        content_type: str,
        code: str,
        from_version: str,
        to_version: str,
    ) -> ContentCompareOut:
        items = list(
            db.scalars(
                select(KnowledgeItem).where(
                    KnowledgeItem.content_type == content_type,
                    KnowledgeItem.code == code,
                    KnowledgeItem.version.in_([from_version, to_version]),
                )
            )
        )
        by_version = {item.version: item for item in items}
        if from_version not in by_version or to_version not in by_version:
            raise LookupError("待比较的内容版本不存在")
        left = _flatten(
            {"title": by_version[from_version].title, "payload": by_version[from_version].payload}
        )
        right = _flatten(
            {"title": by_version[to_version].title, "payload": by_version[to_version].payload}
        )
        changed = {
            path: {"from": left.get(path), "to": right.get(path)}
            for path in sorted(set(left) | set(right))
            if left.get(path) != right.get(path)
        }
        return ContentCompareOut(
            content_type=content_type,
            code=code,
            from_version=from_version,
            to_version=to_version,
            changed_fields=changed,
        )

    def published_catalog(self, db: Session, content_type: str) -> list[KnowledgeItem]:
        return list(
            db.scalars(
                select(KnowledgeItem)
                .where(
                    KnowledgeItem.content_type == content_type,
                    KnowledgeItem.status == "published",
                    KnowledgeItem.is_active.is_(True),
                )
                .order_by(KnowledgeItem.title)
            )
        )


content_service = ContentService()
