from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExperimentCreate(BaseModel):
    action_id: str = Field(min_length=1, max_length=36)
    start_date: date | None = None

    @field_validator("action_id", mode="before")
    @classmethod
    def normalize_action_id(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


MissingReason = Literal[
    "forgot",
    "device_unavailable",
    "physical_discomfort",
    "unplanned_event",
    "other",
]

DiscomfortLevel = Literal["none", "mild", "significant"]


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    observed_on: date
    treatment: bool
    completed: bool
    steps_30m: int | None
    sleep_hours: float | None
    sugary_drinks: int | None
    subjective_score: int | None
    missing_reason: MissingReason | None
    discomfort_level: DiscomfortLevel
    discomfort_details: str | None
    unplanned_event: str | None
    notes: str | None


class ScheduleDay(BaseModel):
    day: int
    date: date
    treatment: bool
    label: str
    recorded: bool = False
    completed: bool = False
    observation: ObservationOut | None = None


class ExperimentOut(BaseModel):
    id: str
    user_id: str
    action_id: str
    action_code: str
    action_title: str
    primary_metric: str
    status: str
    status_label: str
    start_date: date
    end_date: date
    randomization_seed: int
    schedule_version: str
    schedule_locked_at: datetime
    started_at: datetime
    paused_at: datetime | None
    terminated_at: datetime | None
    completed_at: datetime | None
    next_step: str | None
    next_step_selected_at: datetime | None
    progress: int
    recorded_days: int
    completed_days: int
    allowed_transitions: list[str]
    schedule: list[ScheduleDay]


ExperimentTransition = Literal["pause", "resume", "terminate", "complete"]


class ObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_on: date
    treatment: bool | None = None
    completed: bool = False
    steps_30m: int | None = Field(default=None, ge=0, le=20000)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    sugary_drinks: int | None = Field(default=None, ge=0, le=20)
    subjective_score: int | None = Field(default=None, ge=1, le=5)
    missing_reason: MissingReason | None = None
    discomfort_level: DiscomfortLevel = "none"
    discomfort_details: str | None = Field(default=None, max_length=300)
    unplanned_event: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator(
        "discomfort_details",
        "unplanned_event",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None


class ObservationImportIn(BaseModel):
    format: Literal["csv", "json"]
    content: str = Field(min_length=2, max_length=200_000)


class ObservationImportOut(BaseModel):
    message: str
    imported_days: int
    created_days: int
    updated_days: int


NextStepCode = Literal["keep", "adjust", "extend", "stop"]


class NextStepChoiceIn(BaseModel):
    code: NextStepCode


class NextStepChoiceOut(BaseModel):
    experiment_id: str
    code: NextStepCode
    selected_at: datetime


class NextStepOptionOut(BaseModel):
    code: NextStepCode
    title: str
    description: str
    recommended: bool
    selected: bool


class AnalysisPointOut(BaseModel):
    observed_on: date
    group: Literal["reminder", "routine"]
    value: float
    outlier: bool


class ExperimentResultOut(BaseModel):
    experiment_id: str
    analysis_version: str
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
    treatment_median: float | None
    control_median: float | None
    observed_difference: float | None
    completion_rate: float
    effective_rate: float
    valid_days: int
    missing_days: int
    missing_reason_counts: dict[str, int]
    bootstrap_ci_lower: float | None
    bootstrap_ci_upper: float | None
    bootstrap_iterations: int
    outlier_count: int
    outlier_days: list[date]
    sensitivity_difference: float | None
    analysis_points: list[AnalysisPointOut]
    explanation: str
    explanation_source: str
    explanation_policy_version: str
    recommended_next_step: NextStepCode
    next_step_options: list[NextStepOptionOut]
    caveats: list[str]
