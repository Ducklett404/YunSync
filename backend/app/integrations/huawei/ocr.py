from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


class OcrError(RuntimeError):
    def __init__(self, message: str, *, code: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class ExtractedMetric:
    code: str
    name: str
    value: float
    unit: str
    reference_range: str
    raw_text: str
    confidence: float
    source_page: int
    source_bbox: list[float]


@dataclass(frozen=True)
class OcrAnalysis:
    provider: str
    page_count: int
    metrics: list[ExtractedMetric]


class MockOcrClient:
    """Deterministic OCR contract simulator for synthetic files only."""

    provider = "mock_ocr"

    async def analyze(self, content: bytes, _filename: str) -> OcrAnalysis:
        marker = content.decode("latin-1", errors="ignore").lower()
        if "yunsync_scenario:timeout" in marker:
            raise OcrError("合成 OCR 超时，请稍后重试。", code="timeout", retryable=True)
        if "yunsync_scenario:failure" in marker:
            raise OcrError("合成 OCR 无法解析该文件。", code="unreadable", retryable=False)

        confidence_delta = 0.0
        bbox_shift = 0.0
        if "yunsync_scenario:blurred" in marker:
            confidence_delta = -0.34
        elif "yunsync_scenario:rotated" in marker:
            confidence_delta = -0.12
            bbox_shift = 0.04
        elif "yunsync_scenario:low_resolution" in marker:
            confidence_delta = -0.43

        rows = [
            ("bmi", "身体质量指数", 25.8, "kg/m²", "18.5-23.9", 0.98, [0.10, 0.18, 0.28, 0.05]),
            ("fasting_glucose", "空腹血糖", 6.2, "mmol/L", "3.9-6.1", 0.94, [0.10, 0.29, 0.32, 0.05]),
            ("triglyceride", "甘油三酯", 1.9, "mmol/L", "0.45-1.69", 0.91, [0.10, 0.40, 0.34, 0.05]),
            ("hdl_c", "高密度脂蛋白", 1.18, "mmol/L", ">=1.0", 0.88, [0.10, 0.51, 0.31, 0.05]),
            ("systolic_bp", "收缩压", 128.0, "mmHg", "90-139", 0.86, [0.10, 0.62, 0.29, 0.05]),
        ]
        metrics = [
            ExtractedMetric(
                code=code,
                name=name,
                value=value,
                unit=unit,
                reference_range=reference,
                raw_text=f"{name} {value:g} {unit} 参考 {reference}",
                confidence=max(0.01, min(0.99, confidence + confidence_delta)),
                source_page=1,
                source_bbox=[
                    round(min(1.0, coordinate + (bbox_shift if index == 0 else 0.0)), 3)
                    for index, coordinate in enumerate(bbox)
                ],
            )
            for code, name, value, unit, reference, confidence, bbox in rows
        ]
        return OcrAnalysis(provider=self.provider, page_count=1, metrics=metrics)


class HuaweiOcrClient:
    provider = "huawei_ocr"

    async def analyze(self, _content: bytes, _filename: str) -> OcrAnalysis:
        raise OcrError(
            "华为云 OCR 适配器尚未配置，不能将本地合成结果冒充真实识别。",
            code="provider_not_configured",
            retryable=False,
        )


def get_ocr_client():
    if settings.use_mock_ai:
        return MockOcrClient()
    return HuaweiOcrClient()
