from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.health import HealthMetric, HealthReport


class HealthRepository:
    def latest_report(self, db: Session, user_id: str) -> HealthReport | None:
        statement = (
            select(HealthReport)
            .where(HealthReport.user_id == user_id)
            .order_by(HealthReport.created_at.desc(), HealthReport.id.desc())
            .limit(1)
        )
        return db.scalar(statement)

    def reports_for_user(
        self, db: Session, user_id: str, *, limit: int, offset: int
    ) -> tuple[list[HealthReport], int]:
        total = db.scalar(
            select(func.count()).select_from(HealthReport).where(HealthReport.user_id == user_id)
        ) or 0
        statement = (
            select(HealthReport)
            .where(HealthReport.user_id == user_id)
            .order_by(HealthReport.created_at.desc(), HealthReport.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(db.scalars(statement)), total

    def metrics_for_report(self, db: Session, report_id: str) -> list[HealthMetric]:
        statement = (
            select(HealthMetric)
            .where(HealthMetric.report_id == report_id)
            .order_by(HealthMetric.name)
        )
        return list(db.scalars(statement))


health_repository = HealthRepository()
