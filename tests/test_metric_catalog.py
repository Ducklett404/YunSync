import pytest

from app.integrations.huawei.ocr import ExtractedMetric
from app.services.metric_catalog import CATALOG_VERSION, P0_METRICS
from app.services.metric_normalizer import normalize_metric


def extracted_metric(code: str, name: str) -> ExtractedMetric:
    return ExtractedMetric(
        code=code,
        name=name,
        value=5.2,
        unit="mmol/l",
        reference_range="3.9-6.1",
        raw_text=f"{name} 5.2 mmol/l 参考 3.9-6.1",
        confidence=0.9,
        source_page=1,
        source_bbox=[0.1, 0.2, 0.3, 0.1],
    )


def test_p0_catalog_has_stable_unique_codes_and_explicit_draft_version():
    assert CATALOG_VERSION.startswith("v2-p0-draft")
    assert len(P0_METRICS) == 19
    assert len({item.code for item in P0_METRICS}) == len(P0_METRICS)


@pytest.mark.parametrize(
    ("code", "name", "expected_code", "expected_name"),
    [
        ("fpg", "空腹血浆葡萄糖", "fasting_glucose", "空腹血糖"),
        ("", "TG", "triglyceride", "甘油三酯"),
        ("hdl_c", "高密度脂蛋白", "hdl_c", "高密度脂蛋白胆固醇"),
    ],
)
def test_known_aliases_resolve_to_one_metric(code, name, expected_code, expected_name):
    result = normalize_metric(extracted_metric(code, name))
    assert (result.code, result.name) == (expected_code, expected_name)
    assert result.unit == "mmol/L"
    assert result.raw_text.startswith(name)


def test_conflicting_code_and_name_cannot_be_silently_combined():
    with pytest.raises(ValueError, match="代码与名称"):
        normalize_metric(extracted_metric("fpg", "尿酸"))


def test_unknown_metric_keeps_ocr_identity_for_manual_review():
    result = normalize_metric(extracted_metric("thyroid_tsh", "促甲状腺激素"))
    assert result.code == "thyroid_tsh"
    assert result.name == "促甲状腺激素"


def test_blood_urea_nitrogen_is_not_treated_as_urea_without_conversion():
    result = normalize_metric(extracted_metric("bun", "BUN"))
    assert result.code == "bun"
    assert result.name == "BUN"
