from datetime import datetime
from typing import Literal

from pydantic import BaseModel


ACCOUNT_DELETION_CONFIRMATION = "删除我的云循数据"


class AccountDeletionIn(BaseModel):
    confirmation: Literal["删除我的云循数据"]


class ReportDeletionIn(BaseModel):
    confirm_report_id: str


class PrivacyRequestOut(BaseModel):
    id: str
    request_type: str
    status: str
    requested_at: datetime
    execute_after: datetime
    cancelled_at: datetime | None = None
    completed_at: datetime | None = None
    attempt_count: int = 0

    model_config = {"from_attributes": True}


class PrivacyStatusOut(BaseModel):
    active_consent: bool
    pending_deletion: PrivacyRequestOut | None = None
    deletion_grace_hours: int
