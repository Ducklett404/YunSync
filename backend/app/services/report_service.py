from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.huawei.ocr import get_ocr_client
from app.models.audit import AuditLog
from app.models.health import HealthMetric, HealthReport
from app.models.user import UserProfile


ALLOWED_CONTENT_TYPES = {"application/pdf", "image/png", "image/jpeg"}
MAX_FILE_BYTES = 5 * 1024 * 1024


class ReportService:
    async def analyze(self, db: Session, user_id: str, file: UploadFile) -> HealthReport:
        if db.get(UserProfile, user_id) is None:
            raise LookupError("用户不存在")
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError("仅支持 PDF、PNG 或 JPEG 文件")

        content = await file.read(MAX_FILE_BYTES + 1)
        if not content:
            raise ValueError("文件内容不能为空")
        if len(content) > MAX_FILE_BYTES:
            raise ValueError("文件不能超过 5 MB")

        extracted = await get_ocr_client().analyze(content, file.filename or "report")
        report = HealthReport(
            user_id=user_id,
            filename=file.filename or "report",
            source="synthetic" if settings.use_mock_ai else "uploaded",
            status="needs_confirmation",
        )
        db.add(report)
        db.flush()

        for item in extracted:
            db.add(
                HealthMetric(
                    report_id=report.id,
                    user_id=user_id,
                    code=item.code,
                    name=item.name,
                    value=item.value,
                    unit=item.unit,
                    reference_range=item.reference_range,
                    flag=item.flag,
                    confirmed=False,
                )
            )

        db.add(
            AuditLog(
                event_type="report.mock_analyzed" if settings.use_mock_ai else "report.analyzed",
                actor_id=user_id,
                payload={"report_id": report.id, "filename": report.filename, "metric_count": len(extracted)},
            )
        )
        db.commit()
        db.refresh(report)
        return report


report_service = ReportService()
