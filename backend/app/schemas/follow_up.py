"""Explicit two-report comparison without clinical trend interpretation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.metric_history import MetricHistoryPointOut, MetricPairOut


class FollowUpMetricOut(BaseModel):
    code: str
    name: str
    standard_unit: str
    previous: MetricHistoryPointOut | None
    current: MetricHistoryPointOut | None
    pair: MetricPairOut | None
    status: Literal["paired", "only_previous", "only_current"]


class FollowUpComparisonOut(BaseModel):
    previous_report_id: str
    current_report_id: str
    previous_examined_at: datetime | None
    current_examined_at: datetime | None
    days_between: int | None
    rule_version: str
    metrics: list[FollowUpMetricOut]
    limitation: str = "仅显示已确认记录的算术对比；不判断健康改善、恶化或食养效果。"
