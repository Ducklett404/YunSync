from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.health import HealthMetric, HealthReport
from app.repositories.health_repository import health_repository
from app.schemas.common import ApiMessage
from app.schemas.health import ReportAnalysisOut
from app.services.report_service import report_service


router = APIRouter(prefix="/reports", tags=["reports"])


def _serialize_report(db: Session, report: HealthReport) -> ReportAnalysisOut:
    metrics = health_repository.metrics_for_report(db, report.id)
    return ReportAnalysisOut(
        report_id=report.id,
        filename=report.filename,
        source=report.source,
        status=report.status,
        synthetic_notice=(
            "当前 OCR 返回合成演示结果，不代表对上传文件作出医学判断。"
            if report.source == "synthetic"
            else "识别结果需由用户逐项核对，不构成医学诊断。"
        ),
        metrics=metrics,
    )


@router.get("/latest", response_model=ReportAnalysisOut)
def latest_report(user_id: str = "demo-user", db: Session = Depends(get_db)):
    report = health_repository.latest_report(db, user_id)
    if report is None:
        raise HTTPException(status_code=404, detail="尚无体检报告")
    return _serialize_report(db, report)


@router.post("/analyze", response_model=ReportAnalysisOut)
async def analyze_report(
    user_id: str = "demo-user",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        report = await report_service.analyze(db, user_id, file)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _serialize_report(db, report)


@router.post("/{report_id}/confirm", response_model=ApiMessage)
def confirm_report(report_id: str, db: Session = Depends(get_db)):
    report = db.get(HealthReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    report.status = "confirmed"
    db.execute(
        update(HealthMetric).where(HealthMetric.report_id == report_id).values(confirmed=True)
    )
    db.commit()
    return ApiMessage(message="报告字段已确认")
