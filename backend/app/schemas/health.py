from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CriticalMarkerIn(BaseModel):
    status: Literal["unknown", "no", "yes"]


class MetricCorrectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    value: float = Field(ge=-100000, le=100000, allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=32)
    reference_range: str = Field(max_length=64)

    @field_validator("name", "unit")
    @classmethod
    def require_nonblank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("字段不能为空")
        return stripped

    @field_validator("reference_range")
    @classmethod
    def strip_optional_text(cls, value: str) -> str:
        return value.strip()


class HealthMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    value: float
    unit: str
    reference_range: str
    flag: str
    confirmed: bool
    review_status: str
    raw_text: str
    extracted_value: float | None
    extracted_unit: str
    extracted_reference_range: str
    confidence: float
    source_page: int
    source_bbox: list[float]
    measured_at: datetime


class ReportAnalysisOut(BaseModel):
    report_id: str
    filename: str
    source: str
    status: str
    critical_marker_status: str
    critical_marker_reviewed_at: datetime | None
    storage_provider: str
    content_type: str
    file_size: int
    ocr_provider: str
    ocr_status: str
    ocr_attempts: int
    ocr_error_code: str | None
    ocr_page_count: int
    processed_at: datetime | None
    synthetic_notice: str
    metrics: list[HealthMetricOut]


class ReportSummaryOut(BaseModel):
    report_id: str
    filename: str
    status: str
    ocr_status: str
    critical_marker_status: str
    created_at: datetime


class ReportListOut(BaseModel):
    items: list[ReportSummaryOut]
    total: int
    limit: int
    offset: int
