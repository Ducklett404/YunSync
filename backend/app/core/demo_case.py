from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


def validate_demo_case(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"valid": False, "errors": [f"cannot_read_manifest:{type(exc).__name__}"]}
    if not isinstance(payload, dict):
        return {"valid": False, "errors": ["manifest_must_be_object"]}

    if payload.get("synthetic") is not True:
        errors.append("synthetic_must_be_true")
    disclaimer = str(payload.get("disclaimer", ""))
    if "合成" not in disclaimer or "专业审核" not in disclaimer:
        errors.append("disclaimer_missing")
    account = payload.get("account")
    if not isinstance(account, dict) or not account.get("participant_id"):
        errors.append("participant_id_missing")
        account = {}

    reports = payload.get("reports")
    if not isinstance(reports, list) or len(reports) != 2:
        errors.append("exactly_two_reports_required")
        reports = []

    parsed_dates: list[date] = []
    report_metrics: list[dict[str, dict[str, Any]]] = []
    report_ids: set[str] = set()
    for report in reports:
        if not isinstance(report, dict):
            errors.append("report_must_be_object")
            continue
        report_id = str(report.get("id", ""))
        if not report_id or report_id in report_ids:
            errors.append("report_ids_must_be_unique")
        report_ids.add(report_id)
        try:
            parsed_dates.append(date.fromisoformat(str(report.get("exam_date", ""))))
        except ValueError:
            errors.append("invalid_exam_date")
        metrics = report.get("metrics", [])
        by_code: dict[str, dict[str, Any]] = {}
        for metric in metrics if isinstance(metrics, list) else []:
            if not isinstance(metric, dict):
                errors.append("metric_must_be_object")
                continue
            code = str(metric.get("code", ""))
            if not code or code in by_code:
                errors.append("metric_codes_must_be_unique_per_report")
            by_code[code] = metric
            if not all(
                metric.get(field) not in (None, "")
                for field in ("name", "unit", "method", "reference_range")
            ):
                errors.append(f"metric_comparability_fields_missing:{code or 'unknown'}")
        report_metrics.append(by_code)

    if len(parsed_dates) == 2 and parsed_dates[1] <= parsed_dates[0]:
        errors.append("second_report_must_be_later")
    common_codes = set(report_metrics[0]) & set(report_metrics[1]) if len(report_metrics) == 2 else set()
    if len(common_codes) < 3:
        errors.append("at_least_three_common_metrics_required")

    expected_deltas = payload.get("expected_deltas", {})
    if not isinstance(expected_deltas, dict):
        errors.append("expected_deltas_must_be_object")
        expected_deltas = {}
    for code in common_codes:
        first = report_metrics[0][code]
        second = report_metrics[1][code]
        if any(first.get(field) != second.get(field) for field in ("unit", "method", "reference_range")):
            errors.append(f"comparability_changed:{code}")
            continue
        expected = expected_deltas.get(code)
        try:
            actual = round(float(second["value"]) - float(first["value"]), 6)
            expected_value = float(expected)
        except (KeyError, TypeError, ValueError):
            errors.append(f"delta_value_invalid:{code}")
            continue
        if abs(actual - expected_value) > 0.000001:
            errors.append(f"delta_mismatch:{code}")

    forbidden_identity_fields = {"name", "phone", "id_card", "address", "medical_record_number"}
    if forbidden_identity_fields & set(account):
        errors.append("identity_fields_forbidden")

    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "report_count": len(reports),
        "common_metric_count": len(common_codes),
        "synthetic": payload.get("synthetic") is True,
    }
