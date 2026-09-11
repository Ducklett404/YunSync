import asyncio

import pytest

from app.integrations.huawei.ocr import MockOcrClient, OcrError
from app.services.metric_normalizer import normalize_metric


@pytest.mark.parametrize(
    ("scenario", "maximum_confidence"),
    [
        ("standard", 0.99),
        ("blurred", 0.70),
        ("rotated", 0.90),
        ("low_resolution", 0.60),
    ],
)
def test_synthetic_ocr_scenarios_expose_confidence_and_source_location(
    scenario, maximum_confidence
):
    content = f"%PDF YUNSYNC_SCENARIO:{scenario}".encode()
    analysis = asyncio.run(MockOcrClient().analyze(content, f"{scenario}.pdf"))
    normalized = [normalize_metric(metric) for metric in analysis.metrics]

    assert analysis.provider == "mock_ocr"
    assert analysis.page_count == 1
    assert len(normalized) == 5
    assert max(metric.confidence for metric in normalized) <= maximum_confidence
    assert all(metric.source_page == 1 for metric in normalized)
    assert all(len(metric.source_bbox) == 4 for metric in normalized)


@pytest.mark.parametrize(
    ("scenario", "expected_code", "retryable"),
    [("timeout", "timeout", True), ("failure", "unreadable", False)],
)
def test_synthetic_ocr_failure_modes_are_explicit(scenario, expected_code, retryable):
    with pytest.raises(OcrError) as captured:
        asyncio.run(
            MockOcrClient().analyze(
                f"%PDF YUNSYNC_SCENARIO:{scenario}".encode(), f"{scenario}.pdf"
            )
        )

    assert captured.value.code == expected_code
    assert captured.value.retryable is retryable
