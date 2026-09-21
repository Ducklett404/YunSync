"""Read-only alignment of confirmed metrics across report batches."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.services.unit_policy import UnitStatus


class MetricHistoryPointOut(BaseModel):
    report_id: str
    metric_id: str
    report_created_at: datetime
    examined_at: datetime | None
    institution: str
    measured_at: datetime
    value: float
    unit: str
    reference_range: str
    method: str
    standard_value: float | None
    projection_status: UnitStatus


class MetricPairOut(BaseModel):
    previous_report_id: str
    current_report_id: str
    status: Literal[
        "numeric_only",
        "not_projected",
        "duplicate_in_report",
        "metadata_missing",
        "method_changed",
        "reference_range_missing",
        "reference_range_changed",
    ]
    arithmetic_change: float | None
    direction: Literal["higher", "lower", "same"] | None
    reference_range_changed: bool
    source_unit_changed: bool
    institution_changed: bool
    method_changed: bool
    limitations: list[str]


class MetricHistorySeriesOut(BaseModel):
    code: str
    name: str
    standard_unit: str
    points: list[MetricHistoryPointOut]
    latest_pair: MetricPairOut | None


class MetricHistoryOut(BaseModel):
    rule_version: str
    reports_considered: int
    report_limit: int
    series: list[MetricHistorySeriesOut]
