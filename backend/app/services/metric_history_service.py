"""Align confirmed report observations without making clinical trend claims."""

from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.health import HealthMetric, HealthReport
from app.schemas.metric_history import (
    MetricHistoryOut,
    MetricHistoryPointOut,
    MetricHistorySeriesOut,
    MetricPairOut,
)
from app.services.metric_catalog import resolve_metric_code
from app.services.unit_policy import project_metric_unit, unit_key


HISTORY_RULE_VERSION = "v2-history-draft-4"


def _text_key(value: str) -> str:
    return "".join(value.casefold().split())


def _range_key(value: str) -> str:
    normalized = _text_key(value)
    for source, target in (
        ("–", "-"),
        ("—", "-"),
        ("－", "-"),
        ("≤", "<="),
        ("≥", ">="),
        ("＜", "<"),
        ("＞", ">"),
    ):
        normalized = normalized.replace(source, target)
    return normalized


def _time_key(value):
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=None).timestamp()
    return value.timestamp()


def compare_metric_points(
    previous: MetricHistoryPointOut, current: MetricHistoryPointOut, *, duplicate: bool = False
) -> MetricPairOut:
    """Apply the same conservative comparability gate to any two confirmed reports."""
    projected = current.standard_value is not None and previous.standard_value is not None
    previous_range = _range_key(previous.reference_range)
    current_range = _range_key(current.reference_range)
    reference_range_missing = not previous_range or not current_range
    reference_range_changed = previous_range != current_range
    source_unit_changed = unit_key(current.unit) != unit_key(previous.unit)
    institution_changed = _text_key(current.institution) != _text_key(previous.institution)
    method_changed = _text_key(current.method) != _text_key(previous.method)
    metadata_missing = current.examined_at is None or previous.examined_at is None
    institution_missing = not _text_key(current.institution) or not _text_key(previous.institution)
    method_missing = not _text_key(current.method) or not _text_key(previous.method)
    precision_missing = (
        current.reported_precision is None or previous.reported_precision is None
    )
    precision_changed = (
        not precision_missing
        and current.reported_precision != previous.reported_precision
    )
    limitations = ["这里只显示标准单位算术差，不代表健康改善、恶化或食养效果。"]
    if metadata_missing:
        limitations.append("至少一份报告未填写检查日期，无法确定检查先后。")
    if institution_missing:
        limitations.append("至少一份报告未填写检测机构，暂不计算差值。")
    elif institution_changed:
        limitations.append("两份报告的检测机构不同，暂不计算差值并需人工复核。")
    if reference_range_missing:
        limitations.append("至少一份报告未填写参考范围，暂不计算差值。")
    elif reference_range_changed:
        limitations.append("两份报告的参考范围不同，暂不计算差值并需对照原件。")
    if source_unit_changed:
        limitations.append("原报告单位不同，已按当前规则尝试换算。")
    if method_missing:
        limitations.append("至少一项检测方法未填写，暂不计算差值。")
    elif method_changed:
        limitations.append("两次检测方法不同，暂不计算差值。")
    if precision_missing:
        limitations.append("至少一项未记录报告显示小数位，暂不计算差值。")
    elif precision_changed:
        limitations.append("两次报告显示精度不同，暂不计算差值。")
    if duplicate:
        status = "duplicate_in_report"
        limitations.append("同一报告存在多个相同标准指标，无法唯一配对。")
    elif not projected:
        status = "not_projected"
        limitations.append("至少一项单位或名称尚未得到标准数值。")
    elif metadata_missing or institution_missing or method_missing:
        status = "metadata_missing"
    elif institution_changed:
        status = "institution_changed"
    elif method_changed:
        status = "method_changed"
    elif reference_range_missing:
        status = "reference_range_missing"
    elif reference_range_changed:
        status = "reference_range_changed"
    elif precision_missing:
        status = "metadata_missing"
    elif precision_changed:
        status = "precision_changed"
    else:
        status = "numeric_only"
    change = (
        current.standard_value - previous.standard_value
        if status == "numeric_only" and current.standard_value is not None and previous.standard_value is not None
        else None
    )
    return MetricPairOut(
        previous_report_id=previous.report_id,
        current_report_id=current.report_id,
        status=status,
        arithmetic_change=change,
        direction=("higher" if change > 0 else "lower" if change < 0 else "same") if change is not None else None,
        reference_range_changed=reference_range_changed,
        source_unit_changed=source_unit_changed,
        institution_changed=institution_changed,
        method_changed=method_changed,
        precision_missing=precision_missing,
        precision_changed=precision_changed,
        limitations=limitations,
    )


def metric_history(db: Session, user_id: str, *, report_limit: int) -> MetricHistoryOut:
    reports = list(
        db.scalars(
            select(HealthReport)
            .where(HealthReport.user_id == user_id, HealthReport.status == "confirmed")
            .order_by(HealthReport.created_at.desc(), HealthReport.id.desc())
            .limit(report_limit)
        )
    )
    if not reports:
        return MetricHistoryOut(
            rule_version=HISTORY_RULE_VERSION,
            reports_considered=0,
            report_limit=report_limit,
            series=[],
        )

    by_report = {report.id: report for report in reports}
    metrics = list(
        db.scalars(
            select(HealthMetric).where(
                HealthMetric.user_id == user_id,
                HealthMetric.report_id.in_(by_report),
                HealthMetric.confirmed.is_(True),
            )
        )
    )
    by_code: dict[str, list[MetricHistoryPointOut]] = defaultdict(list)
    for metric in metrics:
        definition = resolve_metric_code(metric.code)
        if definition is None:
            continue
        projection = project_metric_unit(
            code=metric.code,
            name=metric.name,
            value=metric.value,
            unit=metric.unit,
            confirmed=metric.confirmed,
        )
        by_code[definition.code].append(
            MetricHistoryPointOut(
                report_id=metric.report_id,
                metric_id=metric.id,
                report_created_at=by_report[metric.report_id].created_at,
                examined_at=by_report[metric.report_id].examined_at,
                institution=by_report[metric.report_id].institution,
                measured_at=metric.measured_at,
                value=metric.value,
                reported_precision=metric.reported_precision,
                unit=metric.unit,
                reference_range=metric.reference_range,
                method=metric.method,
                standard_value=projection.standard_value,
                projection_status=projection.status,
            )
        )

    series = []
    for code, points in sorted(by_code.items()):
        definition = resolve_metric_code(code)
        assert definition is not None
        points.sort(
            key=lambda point: (
                point.examined_at is not None,
                _time_key(point.examined_at or point.report_created_at),
                _time_key(point.report_created_at),
                point.report_id,
                point.metric_id,
            )
        )
        latest_pair = None
        if len({point.report_id for point in points}) >= 2:
            current = points[-1]
            previous = next(point for point in reversed(points) if point.report_id != current.report_id)
            counts = Counter(point.report_id for point in points)
            duplicate = counts[current.report_id] > 1 or counts[previous.report_id] > 1
            latest_pair = compare_metric_points(previous, current, duplicate=duplicate)
        series.append(
            MetricHistorySeriesOut(
                code=code,
                name=definition.name,
                standard_unit=definition.unit,
                points=points,
                latest_pair=latest_pair,
            )
        )

    return MetricHistoryOut(
        rule_version=HISTORY_RULE_VERSION,
        reports_considered=len(reports),
        report_limit=report_limit,
        series=series,
    )
