from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
    measured_at: datetime


class ReportAnalysisOut(BaseModel):
    report_id: str
    filename: str
    source: str
    status: str
    synthetic_notice: str
    metrics: list[HealthMetricOut]

