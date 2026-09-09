from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class ExtractedMetric:
    code: str
    name: str
    value: float
    unit: str
    reference_range: str
    flag: str


class MockOcrClient:
    async def analyze(self, _content: bytes, _filename: str) -> list[ExtractedMetric]:
        return [
            ExtractedMetric("bmi", "身体质量指数", 25.8, "kg/m²", "18.5-23.9", "attention"),
            ExtractedMetric("fasting_glucose", "空腹血糖", 6.2, "mmol/L", "3.9-6.1", "attention"),
            ExtractedMetric("triglyceride", "甘油三酯", 1.9, "mmol/L", "0.45-1.69", "attention"),
            ExtractedMetric("hdl_c", "高密度脂蛋白", 1.18, "mmol/L", ">=1.0", "normal"),
            ExtractedMetric("systolic_bp", "收缩压", 128, "mmHg", "90-139", "normal"),
        ]


class HuaweiOcrClient:
    async def analyze(self, _content: bytes, _filename: str) -> list[ExtractedMetric]:
        raise RuntimeError(
            "Huawei OCR adapter is selected but not configured. "
            "Provide the approved endpoint and authentication implementation first."
        )


def get_ocr_client():
    if settings.use_mock_ai:
        return MockOcrClient()
    return HuaweiOcrClient()

