from datetime import datetime, timedelta, timezone

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.services.unit_policy import UnitStatus, project_metric_unit


class CriticalMarkerIn(BaseModel):
    status: Literal["unknown", "no", "yes"]


class MetricCorrectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    value: float = Field(ge=-100000, le=100000, allow_inf_nan=False)
    reported_precision: int | None = Field(default=None, ge=0, le=6)
    unit: str = Field(min_length=1, max_length=32)
    reference_range: str = Field(max_length=64)
    method: str | None = Field(default=None, max_length=120)

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

    @field_validator("method")
    @classmethod
    def strip_method(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class ManualMetricIn(MetricCorrectionIn):
    code: str = Field(default="", max_length=64)

    @field_validator("code")
    @classmethod
    def strip_code(cls, value: str) -> str:
        return value.strip()


class ManualReportIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    institution: str = Field(default="", max_length=120)
    measured_at: datetime
    metrics: list[ManualMetricIn] = Field(min_length=1, max_length=30)

    @field_validator("title")
    @classmethod
    def require_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("批次名称不能为空")
        return stripped

    @field_validator("institution")
    @classmethod
    def strip_institution(cls, value: str) -> str:
        return value.strip()

    @field_validator("measured_at")
    @classmethod
    def validate_measured_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("检查时间必须包含时区")
        normalized = value.astimezone(timezone.utc)
        if normalized > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("检查时间不能晚于当前时间")
        if normalized.year < 1900:
            raise ValueError("检查时间不能早于 1900 年")
        return normalized


class ReportMetadataIn(BaseModel):
    institution: str = Field(default="", max_length=120)
    examined_at: datetime

    @field_validator("institution")
    @classmethod
    def strip_institution(cls, value: str) -> str:
        return value.strip()

    @field_validator("examined_at")
    @classmethod
    def validate_examined_at(cls, value: datetime) -> datetime:
        return ManualReportIn.validate_measured_at(value)


class UnitProjectionOut(BaseModel):
    status: UnitStatus
    standard_unit: str | None
    standard_value: float | None
    rule_version: str


class HealthMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    value: float
    reported_precision: int | None
    unit: str
    reference_range: str
    method: str
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

    @computed_field
    @property
    def unit_projection(self) -> UnitProjectionOut:
        result = project_metric_unit(
            code=self.code,
            name=self.name,
            value=self.value,
            unit=self.unit,
            confirmed=self.confirmed,
        )
        return UnitProjectionOut(
            status=result.status,
            standard_unit=result.standard_unit,
            standard_value=result.standard_value,
            rule_version=result.rule_version,
        )


class ReportAnalysisOut(BaseModel):
    report_id: str
    filename: str
    institution: str
    examined_at: datetime | None
    source: str
    status: str
    critical_marker_status: str
    critical_marker_reviewed_at: datetime | None
    storage_provider: str
    source_available: bool
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
