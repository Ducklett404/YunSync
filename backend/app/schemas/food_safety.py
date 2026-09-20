from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


AnswerStatus = Literal["unknown", "none", "present"]
SpecialStatus = Literal["unknown", "none", "pregnant", "breastfeeding", "other"]
Readiness = Literal["needs_information", "needs_professional_review", "awaiting_review_rules"]


class FoodSafetyProfileIn(BaseModel):
    allergy_status: AnswerStatus
    allergens: list[str] = Field(default_factory=list, max_length=20)
    medication_status: AnswerStatus
    medications: list[str] = Field(default_factory=list, max_length=20)
    condition_status: AnswerStatus
    conditions: list[str] = Field(default_factory=list, max_length=20)
    clinician_restriction_status: AnswerStatus
    clinician_restrictions: list[str] = Field(default_factory=list, max_length=20)
    special_status: SpecialStatus
    special_details: str = Field(default="", max_length=240)

    @field_validator("allergens", "medications", "conditions", "clinician_restrictions")
    @classmethod
    def normalize_items(cls, items: list[str]) -> list[str]:
        cleaned = [item.strip() for item in items]
        if any(not item or len(item) > 80 for item in cleaned):
            raise ValueError("每项内容必须在 1 到 80 字之间")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("请勿重复填写同一项")
        return cleaned

    @field_validator("special_details")
    @classmethod
    def normalize_special_details(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def details_match_status(self):
        for status_field, items_field in (
            ("allergy_status", "allergens"),
            ("medication_status", "medications"),
            ("condition_status", "conditions"),
            ("clinician_restriction_status", "clinician_restrictions"),
        ):
            status = getattr(self, status_field)
            items = getattr(self, items_field)
            if status == "present" and not items:
                raise ValueError(f"{status_field} 为有时必须填写具体内容")
            if status != "present" and items:
                raise ValueError(f"{status_field} 不为有时不能提交具体内容")
        if self.special_status == "other" and not self.special_details:
            raise ValueError("其他特殊状态必须填写说明")
        if self.special_status != "other" and self.special_details:
            raise ValueError("当前特殊状态无需填写其他说明")
        return self


class FoodSafetyProfileOut(FoodSafetyProfileIn):
    readiness: Readiness
    updated_at: datetime | None
