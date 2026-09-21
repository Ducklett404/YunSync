"""Twenty synthetic structured reports guard V2 normalization behavior."""

import json
from pathlib import Path

import pytest

from app.integrations.huawei.ocr import ExtractedMetric
from app.services.metric_catalog import P0_METRICS
from app.services.metric_normalizer import normalize_metric
from app.services.unit_policy import project_metric_unit


CORPUS_PATH = Path(__file__).parent / "fixtures" / "v2_synthetic_report_regression.json"


def _extracted(report: dict, metric: dict, index: int) -> ExtractedMetric:
    bbox = report.get("source_bbox", [0.1, round(0.08 + index * 0.08, 2), 0.35, 0.05])
    return ExtractedMetric(
        code=metric["code"],
        name=metric["name"],
        value=metric["value"],
        unit=metric["unit"],
        reference_range=metric["reference_range"],
        raw_text=f'{metric["name"]} {metric["value"]} {metric["unit"]} 参考 {metric["reference_range"]}',
        confidence=metric["confidence"],
        source_page=1,
        source_bbox=bbox,
    )


def test_twenty_report_structured_regression_corpus():
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    reports = corpus["reports"]
    assert corpus["source"] == "synthetic"
    assert corpus["contains_personal_data"] is False
    assert len(reports) == 20
    assert len({report["id"] for report in reports}) == 20
    assert len({report["layout"] for report in reports}) >= 10

    covered_p0_codes: set[str] = set()
    projection_statuses: set[str] = set()
    rejected = 0
    low_confidence = 0
    for report in reports:
        extracted = [_extracted(report, metric, index) for index, metric in enumerate(report["metrics"])]
        if report["expected"] == "rejected":
            rejected += 1
            with pytest.raises(ValueError, match=report["expected_error"]):
                [normalize_metric(metric) for metric in extracted]
            continue

        normalized = [normalize_metric(metric) for metric in extracted]
        for source, result, expected in zip(extracted, normalized, report["metrics"], strict=True):
            assert result.code == expected["expected_code"]
            assert result.name == expected["expected_name"]
            assert result.unit == expected["expected_unit"]
            assert result.value == source.value
            assert result.reference_range == source.reference_range
            assert result.raw_text == source.raw_text.strip()
            projection = project_metric_unit(
                code=result.code,
                name=result.name,
                value=result.value,
                unit=result.unit,
                confirmed=True,
            )
            assert projection.status == expected["expected_projection"]
            projection_statuses.add(projection.status)
            if any(definition.code == result.code for definition in P0_METRICS):
                covered_p0_codes.add(result.code)
            if result.confidence < 0.8:
                low_confidence += 1

    assert rejected == 2
    assert covered_p0_codes == {definition.code for definition in P0_METRICS}
    assert {"as_reported", "converted", "unsupported_unit", "outside_catalog"} <= projection_statuses
    assert low_confidence >= 1
