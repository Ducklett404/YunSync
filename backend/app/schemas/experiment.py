from datetime import date

from pydantic import BaseModel, Field


class ExperimentCreate(BaseModel):
    user_id: str = "demo-user"
    action_id: str
    start_date: date | None = None


class ScheduleDay(BaseModel):
    day: int
    date: date
    treatment: bool
    label: str
    completed: bool = False


class ExperimentOut(BaseModel):
    id: str
    user_id: str
    action_id: str
    action_code: str
    action_title: str
    primary_metric: str
    status: str
    start_date: date
    end_date: date
    progress: int
    schedule: list[ScheduleDay]


class ObservationCreate(BaseModel):
    observed_on: date
    treatment: bool | None = None
    completed: bool = False
    steps_30m: int | None = Field(default=None, ge=0, le=20000)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    sugary_drinks: int | None = Field(default=None, ge=0, le=20)
    subjective_score: int | None = Field(default=None, ge=1, le=5)
    missing_reason: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=500)


class ExperimentResultOut(BaseModel):
    experiment_id: str
    status: str
    message: str
    metric_code: str
    metric_label: str
    metric_unit: str
    improvement_direction: str
    treatment_days: int
    control_days: int
    treatment_average: float | None
    control_average: float | None
    observed_difference: float | None
    completion_rate: float
    caveats: list[str]
