from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nickname: str
    role: str
    age_range: str
    goal: str
    sleep_schedule: str
    activity_baseline: str
    constraints: str
    preferences: str
    high_risk: bool
    screening_status: str
    screening_answers: dict[str, bool]
    screened_at: datetime | None


class DemoLoginIn(BaseModel):
    account_id: Literal["demo-student", "demo-reviewer"] = "demo-student"


class SessionOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut


class ConsentNoticeOut(BaseModel):
    version: str
    title: str
    items: list[str]


class ConsentAcceptIn(BaseModel):
    version: str = Field(min_length=1, max_length=32)


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: str
    status: str
    accepted_at: datetime
    withdrawn_at: datetime | None


class AccountStatusOut(BaseModel):
    user: UserOut
    consent: ConsentOut | None
    required_consent_version: str


class ProfileUpdateIn(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=80)
    age_range: Literal["18-24", "25-34", "35-44", "45-54", "55-64", "65+"] | None = None
    goal: str | None = Field(default=None, min_length=1, max_length=120)
    sleep_schedule: str | None = Field(default=None, max_length=120)
    activity_baseline: str | None = Field(default=None, max_length=160)
    constraints: str | None = Field(default=None, max_length=500)
    preferences: str | None = Field(default=None, max_length=500)


class SafetyScreeningIn(BaseModel):
    acute_symptoms: bool
    clinician_restriction: bool
    recent_discomfort: bool
    support_needed: bool


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    actor_id: str
    payload: dict
    created_at: datetime
