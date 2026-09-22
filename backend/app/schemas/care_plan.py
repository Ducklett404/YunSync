from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CarePlanRequest(BaseModel):
    selected_metric_codes: list[str] = Field(default_factory=list, max_length=3)
    servings: int = Field(default=1, ge=1, le=8)
    start_on: date | None = None
    max_minutes: int | None = Field(default=None, ge=5, le=360)
    max_budget_yuan_per_serving: float | None = Field(default=None, ge=0, le=10000)
    available_cookware: list[str] = Field(default_factory=list, max_length=30)
    preferred_taste: str = Field(default="", max_length=80)
    region: str = Field(default="", max_length=80)
    unavailable_ingredient_codes: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("selected_metric_codes", "available_cookware", "unavailable_ingredient_codes")
    @classmethod
    def clean_list(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(set(cleaned)) != len(cleaned):
            raise ValueError("列表项不能为空或重复")
        return cleaned

    @field_validator("preferred_taste", "region")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()

class PlanGoal(BaseModel):
    metric_id: str
    code: str
    name: str
    value: float
    unit: str
    reference_range: str
    report_date: str
    statement: str


class PlanAlternative(BaseModel):
    code: str
    version: str
    title: str
    grams: float
    note: str


class PlanMaterial(BaseModel):
    code: str
    version: str
    title: str
    grams: float
    edible_part: str
    preparation: str
    substituted_for: str | None = None
    alternatives: list[PlanAlternative]


class PlanRecipe(BaseModel):
    code: str
    version: str
    title: str
    servings: int
    score: float
    score_breakdown: dict[str, float]
    matched_metric_codes: list[str]
    reason: str
    goal_statement: str
    materials: list[PlanMaterial]
    preprocessing: list[str]
    steps: list[dict]
    frequency: str
    max_weekly_uses: int
    cycle: str
    serving_note: str
    caution: str
    nutrition_tags: list[str]
    dining_alternatives: list[str]
    total_minutes: int
    estimated_cost_yuan_per_serving: float | None
    source_refs: list[str]
    review_id: str
    published_at: datetime


class PlanDay(BaseModel):
    day: int
    date: date
    recipe_code: str
    recipe_version: str
    servings: int


class ShoppingItem(BaseModel):
    code: str
    version: str
    title: str
    total_grams: float
    edible_part: str


class CarePlanSnapshot(BaseModel):
    schema_version: Literal["care-plan-v1"] = "care-plan-v1"
    ranking_policy_version: Literal["care-plan-rank-v1"] = "care-plan-rank-v1"
    report_id: str
    report_date: str
    safety_rule_version: str
    goals: list[PlanGoal] = Field(min_length=1, max_length=3)
    recipes: list[PlanRecipe] = Field(min_length=3, max_length=7)
    schedule: list[PlanDay] = Field(min_length=7, max_length=7)
    shopping_list: list[ShoppingItem]
    contraindication_refs: list[str]
    source_refs: list[str]
    constraints: CarePlanRequest
    explanation_mode: Literal["reviewed_template"] = "reviewed_template"
    general_principle: str
    professional_consultation: str
    follow_up: str
    disclaimer: str


class CarePlanOut(BaseModel):
    id: str
    report_id: str
    status: Literal["READY", "ACTIVE", "PAUSED"]
    snapshot: CarePlanSnapshot
    created_at: datetime
    activated_at: datetime | None
    paused_at: datetime | None

    model_config = {"from_attributes": True}
