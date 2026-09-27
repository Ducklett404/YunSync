"""Synthetic comparability matrix for conservative cross-report arithmetic."""

from datetime import datetime, timezone

from app.schemas.metric_history import MetricHistoryPointOut
from app.services.metric_history_service import compare_metric_points
from app.services.metric_normalizer import infer_reported_precision


NOW = datetime(2026, 9, 25, tzinfo=timezone.utc)


def point(
    report_id: str,
    value: float,
    *,
    institution: str = "合成检测机构",
    method: str = "合成检测方法",
    precision: int | None = 1,
    unit: str = "μmol/L",
) -> MetricHistoryPointOut:
    return MetricHistoryPointOut(
        report_id=report_id,
        metric_id=f"metric-{report_id}",
        report_created_at=NOW,
        examined_at=NOW,
        institution=institution,
        measured_at=NOW,
        value=value,
        reported_precision=precision,
        unit=unit,
        reference_range="208-428",
        method=method,
        standard_value=value,
        projection_status="as_reported",
    )


def test_equivalent_unit_spelling_does_not_create_false_change():
    result = compare_metric_points(
        point("old", 360, unit="μmol/L"),
        point("new", 380, unit="umol/l"),
    )

    assert result.status == "numeric_only"
    assert result.arithmetic_change == 20
    assert result.source_unit_changed is False


def test_institution_change_blocks_arithmetic_until_reviewed():
    result = compare_metric_points(
        point("old", 360, institution="合成机构甲"),
        point("new", 380, institution="合成机构乙"),
    )

    assert result.status == "institution_changed"
    assert result.arithmetic_change is None
    assert result.institution_changed is True


def test_precision_change_or_missing_precision_blocks_arithmetic():
    changed = compare_metric_points(
        point("old", 5.6, precision=1),
        point("new", 5.65, precision=2),
    )
    missing = compare_metric_points(
        point("old", 5.6, precision=1),
        point("new", 5.7, precision=None),
    )

    assert changed.status == "precision_changed"
    assert changed.precision_changed is True
    assert changed.arithmetic_change is None
    assert missing.status == "metadata_missing"
    assert missing.precision_missing is True
    assert missing.arithmetic_change is None


def test_precision_is_read_from_synthetic_ocr_source_text_only():
    assert infer_reported_precision("尿酸 360.00 μmol/L 参考 208-428", 360) == 2
    assert infer_reported_precision("HbA1c 5,60 %", 5.6) == 2
    assert infer_reported_precision("只有指标名称，没有原始数值", 5.6) is None
