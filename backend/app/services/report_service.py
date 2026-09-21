from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.huawei.obs import (
    LocalPrivateStorageClient,
    ObjectStorageError,
    get_object_storage,
)
from app.integrations.huawei.ocr import ExtractedMetric, OcrAnalysis, OcrError, get_ocr_client
from app.models.audit import AuditLog
from app.models.health import HealthMetric, HealthReport
from app.models.user import UserProfile
from app.repositories.health_repository import health_repository
from app.schemas.health import ManualReportIn, MetricCorrectionIn, ReportMetadataIn
from app.services.metric_normalizer import derive_flag, normalize_metric
from app.services.metric_catalog import CATALOG_VERSION
from app.services.unit_policy import BLOCKING_UNIT_STATUSES, project_metric_unit


ALLOWED_CONTENT_TYPES = {
    "application/pdf": {".pdf"},
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
}
MAX_FILE_BYTES = 5 * 1024 * 1024


class ReportProcessingError(RuntimeError):
    def __init__(self, message: str, *, report_id: str, code: str):
        super().__init__(message)
        self.report_id = report_id
        self.code = code


class ReportConflictError(RuntimeError):
    pass


def _safe_filename(filename: str | None, content_type: str) -> str:
    candidate = (filename or "report").replace("\\", "/").split("/")[-1].strip()
    candidate = "".join(char for char in candidate if char >= " " and char not in '<>:"|?*')
    if not candidate:
        candidate = "report"
    suffix = Path(candidate).suffix.lower()
    if suffix not in ALLOWED_CONTENT_TYPES[content_type]:
        raise ValueError("文件扩展名与声明格式不一致")
    stem_limit = 120 - len(suffix)
    return f"{Path(candidate).stem[:stem_limit]}{suffix}"


def _validate_signature(content: bytes, content_type: str) -> None:
    signatures = {
        "application/pdf": (b"%PDF",),
        "image/png": (b"\x89PNG\r\n\x1a\n",),
        "image/jpeg": (b"\xff\xd8\xff",),
    }
    if not any(content.startswith(signature) for signature in signatures[content_type]):
        raise ValueError("文件内容与声明格式不一致")


def _same_instant(left: datetime | None, right: datetime | None) -> bool:
    def normalized(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    return normalized(left) == normalized(right)


class ReportService:
    def create_manual(
        self, db: Session, user_id: str, payload: ManualReportIn
    ) -> HealthReport:
        if db.get(UserProfile, user_id) is None:
            raise LookupError("用户不存在")

        normalized = []
        for index, item in enumerate(payload.metrics):
            code = item.code or f"manual_{sha256(item.name.casefold().encode('utf-8')).hexdigest()[:12]}"
            reference_text = item.reference_range or "未填写"
            normalized.append(
                (
                    item,
                    normalize_metric(
                        ExtractedMetric(
                            code=code,
                            name=item.name,
                            value=item.value,
                            unit=item.unit,
                            reference_range=item.reference_range,
                            raw_text=f"手工录入：{item.name} {item.value:g} {item.unit}；参考范围 {reference_text}",
                            confidence=1.0,
                            source_page=1,
                            source_bbox=[0.0, round(min(0.95, index * 0.03), 2), 0.0, 0.0],
                        )
                    ),
                )
            )
        codes = [result.code for _, result in normalized]
        if len(codes) != len(set(codes)):
            raise ValueError("同一批次不能重复录入同一个标准指标")

        now = datetime.now(timezone.utc)
        report = HealthReport(
            id=str(uuid4()),
            user_id=user_id,
            filename=payload.title,
            institution=payload.institution,
            examined_at=payload.measured_at,
            source="manual",
            status="needs_confirmation",
            storage_provider="manual_entry",
            storage_key=None,
            content_type="application/json",
            file_size=0,
            content_sha256="",
            ocr_provider="manual_entry",
            ocr_status="completed",
            ocr_attempts=0,
            ocr_page_count=0,
            processed_at=now,
        )
        db.add(report)
        db.flush()
        for source, result in normalized:
            db.add(
                HealthMetric(
                    report_id=report.id,
                    user_id=user_id,
                    code=result.code,
                    name=result.name,
                    value=result.value,
                    unit=result.unit,
                    reference_range=result.reference_range,
                    method=source.method or "",
                    flag=result.flag,
                    confirmed=False,
                    review_status="pending",
                    raw_text=result.raw_text,
                    extracted_value=source.value,
                    extracted_unit=source.unit,
                    extracted_reference_range=source.reference_range,
                    confidence=1.0,
                    source_page=1,
                    source_bbox=result.source_bbox,
                    measured_at=payload.measured_at,
                )
            )
        db.add(
            AuditLog(
                event_type="report.manual_created",
                actor_id=user_id,
                payload={
                    "report_id": report.id,
                    "metric_count": len(normalized),
                    "metric_catalog_version": CATALOG_VERSION,
                },
            )
        )
        db.commit()
        db.refresh(report)
        return report

    def update_metadata(
        self,
        db: Session,
        user_id: str,
        report_id: str,
        payload: ReportMetadataIn,
    ) -> HealthReport:
        report = self._owned_report(db, user_id, report_id)
        changed_fields = []
        if report.institution != payload.institution:
            changed_fields.append("institution")
        if not _same_instant(report.examined_at, payload.examined_at):
            changed_fields.append("examined_at")
        if not changed_fields:
            return report

        report.institution = payload.institution
        report.examined_at = payload.examined_at
        if "examined_at" in changed_fields:
            for metric in health_repository.metrics_for_report(db, report.id):
                metric.measured_at = payload.examined_at
        if report.status == "confirmed":
            report.status = "needs_confirmation"
        db.add(
            AuditLog(
                event_type="report.metadata_corrected",
                actor_id=user_id,
                payload={"report_id": report.id, "changed_fields": changed_fields},
            )
        )
        db.commit()
        db.refresh(report)
        return report

    async def analyze(self, db: Session, user_id: str, file: UploadFile) -> HealthReport:
        if db.get(UserProfile, user_id) is None:
            raise LookupError("用户不存在")
        content_type = file.content_type or ""
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError("仅支持 PDF、PNG 或 JPEG 文件")

        filename = _safe_filename(file.filename, content_type)
        content = await file.read(MAX_FILE_BYTES + 1)
        if not content:
            raise ValueError("文件内容不能为空")
        if len(content) > MAX_FILE_BYTES:
            raise ValueError("文件不能超过 5 MB")
        _validate_signature(content, content_type)

        storage = get_object_storage()
        stored = storage.put_private(
            content,
            user_id=user_id,
            suffix=Path(filename).suffix,
        )
        report = HealthReport(
            id=str(uuid4()),
            user_id=user_id,
            filename=filename,
            source="synthetic" if settings.use_mock_ai else "uploaded",
            status="processing",
            storage_provider=stored.provider,
            storage_key=stored.key,
            content_type=content_type,
            file_size=stored.size,
            content_sha256=stored.content_sha256,
            ocr_provider="mock_ocr" if settings.use_mock_ai else "huawei_ocr",
            ocr_status="processing",
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return await self._process_ocr(db, report, content)

    async def retry(self, db: Session, user_id: str, report_id: str) -> HealthReport:
        report = self._owned_report(db, user_id, report_id)
        if report.ocr_status != "failed":
            raise ReportConflictError("只有识别失败的报告可以重试")
        content = self.source_bytes(report)
        report.status = "processing"
        report.ocr_status = "processing"
        report.ocr_error_code = None
        db.commit()
        return await self._process_ocr(db, report, content)

    async def _process_ocr(
        self, db: Session, report: HealthReport, content: bytes
    ) -> HealthReport:
        client = get_ocr_client()
        analysis: OcrAnalysis | None = None
        final_error: OcrError | None = None

        for attempt in range(1, settings.ocr_max_attempts + 1):
            report.ocr_attempts = attempt
            try:
                analysis = await asyncio.wait_for(
                    client.analyze(content, report.filename),
                    timeout=settings.ocr_timeout_seconds,
                )
                break
            except asyncio.TimeoutError:
                final_error = OcrError(
                    "OCR 处理超时，请稍后重试。", code="timeout", retryable=True
                )
            except OcrError as exc:
                final_error = exc
            except Exception:
                final_error = OcrError(
                    "OCR 服务暂时不可用，请稍后重试。",
                    code="provider_error",
                    retryable=True,
                )
            if not final_error.retryable or attempt == settings.ocr_max_attempts:
                break

        if analysis is None:
            assert final_error is not None
            self._record_failure(db, report, final_error)

        try:
            normalized = [normalize_metric(item) for item in analysis.metrics]
        except ValueError as exc:
            self._record_failure(
                db,
                report,
                OcrError(str(exc), code="invalid_provider_payload", retryable=False),
            )
        if not normalized:
            self._record_failure(
                db,
                report,
                OcrError("OCR 未提取到可核对指标。", code="no_metrics", retryable=False),
            )
        metric_codes = [item.code for item in normalized]
        if len(metric_codes) != len(set(metric_codes)):
            self._record_failure(
                db,
                report,
                OcrError(
                    "OCR 返回了重复指标代码，已停止入库，请重试或检查服务配置。",
                    code="duplicate_metric_codes",
                    retryable=False,
                ),
            )

        for item in normalized:
            db.add(
                HealthMetric(
                    report_id=report.id,
                    user_id=report.user_id,
                    code=item.code,
                    name=item.name,
                    value=item.value,
                    unit=item.unit,
                    reference_range=item.reference_range,
                    flag=item.flag,
                    confirmed=False,
                    review_status="pending",
                    raw_text=item.raw_text,
                    extracted_value=item.value,
                    extracted_unit=item.unit,
                    extracted_reference_range=item.reference_range,
                    confidence=item.confidence,
                    source_page=item.source_page,
                    source_bbox=item.source_bbox,
                )
            )

        report.status = "needs_confirmation"
        report.ocr_status = "completed"
        report.ocr_provider = analysis.provider
        report.ocr_page_count = analysis.page_count
        report.ocr_error_code = None
        report.processed_at = datetime.now(timezone.utc)
        db.add(
            AuditLog(
                event_type="report.mock_analyzed" if report.source == "synthetic" else "report.analyzed",
                actor_id=report.user_id,
                payload={
                    "report_id": report.id,
                    "source": report.source,
                    "storage_provider": report.storage_provider,
                    "ocr_provider": report.ocr_provider,
                    "metric_count": len(normalized),
                    "metric_catalog_version": CATALOG_VERSION,
                    "attempts": report.ocr_attempts,
                },
            )
        )
        db.commit()
        db.refresh(report)
        return report

    def _record_failure(self, db: Session, report: HealthReport, error: OcrError) -> None:
        report.status = "ocr_failed"
        report.ocr_status = "failed"
        report.ocr_error_code = error.code
        report.processed_at = datetime.now(timezone.utc)
        db.add(
            AuditLog(
                event_type="report.ocr_failed",
                actor_id=report.user_id,
                payload={
                    "report_id": report.id,
                    "ocr_provider": report.ocr_provider,
                    "error_code": error.code,
                    "attempts": report.ocr_attempts,
                },
            )
        )
        db.commit()
        raise ReportProcessingError(
            str(error), report_id=report.id, code=error.code
        ) from error

    def confirm_metric(
        self, db: Session, user_id: str, report_id: str, metric_id: str
    ) -> HealthMetric:
        report = self._owned_report(db, user_id, report_id)
        if report.ocr_status != "completed":
            raise ReportConflictError("OCR 未完成，不能确认字段")
        metric = self._owned_metric(db, user_id, report_id, metric_id)
        if not metric.confirmed:
            metric.confirmed = True
            metric.review_status = "confirmed"
            db.add(
                AuditLog(
                    event_type="report.metric_confirmed",
                    actor_id=user_id,
                    payload={"report_id": report_id, "metric_id": metric_id},
                )
            )
            db.commit()
            db.refresh(metric)
        return metric

    def correct_metric(
        self,
        db: Session,
        user_id: str,
        report_id: str,
        metric_id: str,
        payload: MetricCorrectionIn,
    ) -> HealthMetric:
        report = self._owned_report(db, user_id, report_id)
        if report.ocr_status != "completed":
            raise ReportConflictError("OCR 未完成，不能修正字段")
        metric = self._owned_metric(db, user_id, report_id, metric_id)
        requested_method = metric.method if payload.method is None else payload.method
        content_changed_fields = [
            field
            for field in ("name", "value", "unit", "reference_range")
            if getattr(metric, field) != getattr(payload, field)
        ]
        method_changed = metric.method != requested_method
        if report.status == "confirmed":
            current_projection = project_metric_unit(
                code=metric.code,
                name=metric.name,
                value=metric.value,
                unit=metric.unit,
                confirmed=metric.confirmed,
            )
            unit_recovery = current_projection.status in BLOCKING_UNIT_STATUSES
            method_only = method_changed and not content_changed_fields
            if not unit_recovery and not method_only:
                raise ReportConflictError("已完成确认的报告不能继续修改")
            report.status = "needs_confirmation"
            db.add(
                AuditLog(
                    event_type=(
                        "report.reopened_for_unit_review"
                        if unit_recovery
                        else "report.reopened_for_method_review"
                    ),
                    actor_id=user_id,
                    payload={"report_id": report_id, "metric_id": metric_id},
                )
            )
        changed_fields = [*content_changed_fields]
        if method_changed:
            changed_fields.append("method")
        metric.name = payload.name
        metric.value = payload.value
        metric.unit = payload.unit
        metric.reference_range = payload.reference_range
        metric.method = requested_method
        metric.flag = derive_flag(payload.value, payload.reference_range)
        metric.confirmed = True
        metric.review_status = "corrected" if changed_fields else "confirmed"
        db.add(
            AuditLog(
                event_type="report.metric_corrected" if changed_fields else "report.metric_confirmed",
                actor_id=user_id,
                payload={
                    "report_id": report_id,
                    "metric_id": metric_id,
                    "changed_fields": changed_fields,
                },
            )
        )
        db.commit()
        db.refresh(metric)
        return metric

    def finalize(self, db: Session, user_id: str, report_id: str) -> HealthReport:
        report = self._owned_report(db, user_id, report_id)
        if report.ocr_status != "completed":
            raise ReportConflictError("OCR 未完成，不能完成报告确认")
        metrics = health_repository.metrics_for_report(db, report_id)
        if not metrics:
            raise ReportConflictError("报告没有可确认指标")
        pending_count = sum(not metric.confirmed for metric in metrics)
        if pending_count:
            raise ReportConflictError(f"仍有 {pending_count} 个字段未逐项确认")
        unit_conflicts = sum(
            project_metric_unit(
                code=metric.code,
                name=metric.name,
                value=metric.value,
                unit=metric.unit,
                confirmed=metric.confirmed,
            ).status in BLOCKING_UNIT_STATUSES
            for metric in metrics
        )
        if unit_conflicts:
            raise ReportConflictError(f"仍有 {unit_conflicts} 个标准指标的名称或单位待核对")
        if report.status != "confirmed":
            report.status = "confirmed"
            db.add(
                AuditLog(
                    event_type="report.confirmed",
                    actor_id=user_id,
                    payload={"report_id": report_id, "metric_count": len(metrics)},
                )
            )
            db.commit()
            db.refresh(report)
        return report

    def set_critical_marker(
        self, db: Session, user_id: str, report_id: str, status: str
    ) -> HealthReport:
        report = self._owned_report(db, user_id, report_id)
        if report.critical_marker_status == status:
            return report
        report.critical_marker_status = status
        report.critical_marker_reviewed_at = (
            datetime.now(timezone.utc) if status != "unknown" else None
        )
        db.add(
            AuditLog(
                event_type="report.critical_marker_reviewed",
                actor_id=user_id,
                payload={"report_id": report_id, "field": "critical_marker_status"},
            )
        )
        db.commit()
        db.refresh(report)
        return report

    def source_bytes(self, report: HealthReport) -> bytes:
        if not report.storage_key:
            raise ReportConflictError("该报告没有可下载的源文件")
        if report.storage_provider != "local_private":
            return get_object_storage().read_private(report.storage_key)
        return LocalPrivateStorageClient().read_private(report.storage_key)

    @staticmethod
    def _owned_report(db: Session, user_id: str, report_id: str) -> HealthReport:
        report = db.get(HealthReport, report_id)
        if report is None or report.user_id != user_id:
            raise LookupError("报告不存在")
        return report

    @staticmethod
    def _owned_metric(
        db: Session, user_id: str, report_id: str, metric_id: str
    ) -> HealthMetric:
        metric = db.get(HealthMetric, metric_id)
        if (
            metric is None
            or metric.user_id != user_id
            or metric.report_id != report_id
        ):
            raise LookupError("报告字段不存在")
        return metric


report_service = ReportService()
