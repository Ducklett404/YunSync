"""Compare two owned confirmed reports using the existing conservative rules."""

from sqlalchemy.orm import Session

from app.models.health import HealthMetric, HealthReport
from app.repositories.health_repository import health_repository
from app.schemas.follow_up import FollowUpComparisonOut, FollowUpMetricOut
from app.schemas.metric_history import MetricHistoryPointOut
from app.services.metric_catalog import resolve_metric_code
from app.services.metric_history_service import HISTORY_RULE_VERSION, compare_metric_points
from app.services.unit_policy import project_metric_unit


class FollowUpConflict(RuntimeError):
    pass


def _point(report: HealthReport, metric: HealthMetric) -> MetricHistoryPointOut:
    projection = project_metric_unit(
        code=metric.code, name=metric.name, value=metric.value,
        unit=metric.unit, confirmed=metric.confirmed,
    )
    return MetricHistoryPointOut(
        report_id=report.id, metric_id=metric.id,
        report_created_at=report.created_at, examined_at=report.examined_at,
        institution=report.institution, measured_at=metric.measured_at,
        value=metric.value, reported_precision=metric.reported_precision,
        unit=metric.unit, reference_range=metric.reference_range,
        method=metric.method, standard_value=projection.standard_value,
        projection_status=projection.status,
    )


def compare_reports(
    db: Session, user_id: str, previous_report_id: str, current_report_id: str
) -> FollowUpComparisonOut:
    if previous_report_id == current_report_id:
        raise FollowUpConflict("请选择两份不同的报告")
    previous = db.get(HealthReport, previous_report_id)
    current = db.get(HealthReport, current_report_id)
    if previous is None or current is None or previous.user_id != user_id or current.user_id != user_id:
        raise LookupError("报告不存在")
    if previous.status != "confirmed" or current.status != "confirmed":
        raise FollowUpConflict("两份报告均须完成整份核对")
    if previous.examined_at and current.examined_at:
        if current.examined_at < previous.examined_at:
            raise FollowUpConflict("新报告检查日期不能早于旧报告")
    elif current.created_at < previous.created_at:
        raise FollowUpConflict("缺少检查日期时，请按上传先后选择报告")

    by_report: dict[str, dict[str, list[MetricHistoryPointOut]]] = {}
    for report in (previous, current):
        grouped: dict[str, list[MetricHistoryPointOut]] = {}
        for metric in health_repository.metrics_for_report(db, report.id):
            definition = resolve_metric_code(metric.code)
            if metric.confirmed and definition is not None:
                grouped.setdefault(definition.code, []).append(_point(report, metric))
        by_report[report.id] = grouped

    metrics = []
    for code in sorted(set(by_report[previous.id]) | set(by_report[current.id])):
        definition = resolve_metric_code(code)
        assert definition is not None
        old_points = by_report[previous.id].get(code, [])
        new_points = by_report[current.id].get(code, [])
        old = old_points[0] if len(old_points) == 1 else None
        new = new_points[0] if len(new_points) == 1 else None
        pair = compare_metric_points(old, new) if old and new else None
        status = "paired" if old and new else "only_previous" if old else "only_current"
        metrics.append(FollowUpMetricOut(
            code=code, name=definition.name, standard_unit=definition.unit,
            previous=old, current=new, pair=pair, status=status,
        ))
    days_between = (
        (current.examined_at.date() - previous.examined_at.date()).days
        if previous.examined_at and current.examined_at else None
    )
    return FollowUpComparisonOut(
        previous_report_id=previous.id, current_report_id=current.id,
        previous_examined_at=previous.examined_at, current_examined_at=current.examined_at,
        days_between=days_between, rule_version=HISTORY_RULE_VERSION, metrics=metrics,
    )
