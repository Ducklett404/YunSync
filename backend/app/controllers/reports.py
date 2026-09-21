from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.security import require_active_participant
from app.db.session import get_db
from app.integrations.huawei.obs import ObjectStorageError
from app.models.health import HealthReport
from app.models.user import UserProfile
from app.repositories.health_repository import health_repository
from app.schemas.common import ApiMessage
from app.schemas.health import (
    CriticalMarkerIn,
    HealthMetricOut,
    ManualReportIn,
    MetricCorrectionIn,
    ReportAnalysisOut,
    ReportListOut,
    ReportMetadataIn,
    ReportSummaryOut,
)
from app.services.report_service import (
    ReportConflictError,
    ReportProcessingError,
    report_service,
)


router = APIRouter(prefix="/reports", tags=["reports"])


def _serialize_report(db: Session, report: HealthReport) -> ReportAnalysisOut:
    metrics = health_repository.metrics_for_report(db, report.id)
    return ReportAnalysisOut(
        report_id=report.id,
        filename=report.filename,
        institution=report.institution,
        examined_at=report.examined_at,
        source=report.source,
        status=report.status,
        critical_marker_status=report.critical_marker_status,
        critical_marker_reviewed_at=report.critical_marker_reviewed_at,
        storage_provider=report.storage_provider,
        source_available=bool(report.storage_key),
        content_type=report.content_type,
        file_size=report.file_size,
        ocr_provider=report.ocr_provider,
        ocr_status=report.ocr_status,
        ocr_attempts=report.ocr_attempts,
        ocr_error_code=report.ocr_error_code,
        ocr_page_count=report.ocr_page_count,
        processed_at=report.processed_at,
        synthetic_notice=(
            "当前 OCR 返回合成演示结果，不代表对上传文件作出医学判断。"
            if report.source == "synthetic"
            else "该批次由用户手工录入，仍需逐项核对，不构成医学诊断。"
            if report.source == "manual"
            else "识别结果需由用户逐项核对，不构成医学诊断。"
        ),
        metrics=metrics,
    )


@router.get("/latest", response_model=ReportAnalysisOut)
def latest_report(
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    report = health_repository.latest_report(db, user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="尚无体检报告")
    return _serialize_report(db, report)


@router.get("", response_model=ReportListOut)
def list_reports(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    reports, total = health_repository.reports_for_user(
        db, user.id, limit=limit, offset=offset
    )
    return ReportListOut(
        items=[
            ReportSummaryOut(
                report_id=report.id,
                filename=report.filename,
                status=report.status,
                ocr_status=report.ocr_status,
                critical_marker_status=report.critical_marker_status,
                created_at=report.created_at,
            )
            for report in reports
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{report_id}", response_model=ReportAnalysisOut)
def get_report(
    report_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        report = report_service._owned_report(db, user.id, report_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_report(db, report)


@router.post("/analyze", response_model=ReportAnalysisOut)
async def analyze_report(
    file: UploadFile = File(...),
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        report = await report_service.analyze(db, user.id, file)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ObjectStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ReportProcessingError as exc:
        raise HTTPException(
            status_code=503,
            detail={"message": str(exc), "report_id": exc.report_id, "code": exc.code},
        ) from exc
    return _serialize_report(db, report)


@router.post("/manual", response_model=ReportAnalysisOut)
def create_manual_report(
    payload: ManualReportIn,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        report = report_service.create_manual(db, user.id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_report(db, report)


@router.patch("/{report_id}/metadata", response_model=ReportAnalysisOut)
def update_report_metadata(
    report_id: str,
    payload: ReportMetadataIn,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        report = report_service.update_metadata(db, user.id, report_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_report(db, report)


@router.post("/{report_id}/retry", response_model=ReportAnalysisOut)
async def retry_report(
    report_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        report = await report_service.retry(db, user.id, report_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReportConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ObjectStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ReportProcessingError as exc:
        raise HTTPException(
            status_code=503,
            detail={"message": str(exc), "report_id": exc.report_id, "code": exc.code},
        ) from exc
    return _serialize_report(db, report)


@router.get("/{report_id}/source")
def download_source(
    report_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        report = report_service._owned_report(db, user.id, report_id)
        content = report_service.source_bytes(report)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReportConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ObjectStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=report.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(report.filename)}",
            "Cache-Control": "private, no-store",
        },
    )


@router.post(
    "/{report_id}/metrics/{metric_id}/confirm", response_model=HealthMetricOut
)
def confirm_metric(
    report_id: str,
    metric_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        return report_service.confirm_metric(db, user.id, report_id, metric_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReportConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch(
    "/{report_id}/metrics/{metric_id}", response_model=HealthMetricOut
)
def correct_metric(
    report_id: str,
    metric_id: str,
    payload: MetricCorrectionIn,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        return report_service.correct_metric(db, user.id, report_id, metric_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReportConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{report_id}/confirm", response_model=ApiMessage)
def confirm_report(
    report_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        report_service.finalize(db, user.id, report_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReportConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiMessage(message="报告字段已逐项确认")


@router.patch("/{report_id}/critical-marker", response_model=ReportAnalysisOut)
def update_critical_marker(
    report_id: str,
    payload: CriticalMarkerIn,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    try:
        report = report_service.set_critical_marker(db, user.id, report_id, payload.status)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_report(db, report)
