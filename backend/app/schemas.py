from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator


Feeling = Literal[
    "正常",
    "有点着凉",
    "胃口较差",
    "睡眠不足",
    "口干",
    "排便不规律",
    "其他轻微不适",
]


def _clean(values: list[str], limit: int) -> list[str]:
    result: list[str] = []
    for raw in values:
        value = raw.strip()
        if value and value not in result:
            result.append(value)
        if len(result) == limit:
            break
    return result


class TodayRecommendationRequest(BaseModel):
    city: str = Field(min_length=1, max_length=40)
    region: str = Field(default="全国", min_length=1, max_length=20)
    date: dt.date | None = None
    feelings: list[Feeling] = Field(default_factory=lambda: ["正常"], max_length=4)
    allergies: list[str] = Field(default_factory=list, max_length=20)
    dietaryRestrictions: list[str] = Field(default_factory=list, max_length=20)
    preferences: list[str] = Field(default_factory=list, max_length=10)
    constitutionTags: list[str] = Field(default_factory=list, max_length=10)
    recentRecipeIds: list[str] = Field(default_factory=list, max_length=20)

    @field_validator(
        "allergies",
        "dietaryRestrictions",
        "preferences",
        "constitutionTags",
        "recentRecipeIds",
    )
    @classmethod
    def clean_lists(cls, value: list[str]) -> list[str]:
        return _clean(value, 20)


class PantryRecommendationRequest(BaseModel):
    ingredients: list[str] = Field(min_length=1, max_length=15)
    tools: list[str] = Field(min_length=1, max_length=15)
    maxMinutes: int = Field(default=45, ge=5, le=240)
    targetServings: Literal[1, 2, 4] = 2
    maxAdditionalIngredients: Literal[0, 1, 2] = 1
    allergies: list[str] = Field(default_factory=list, max_length=20)
    dietaryRestrictions: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("ingredients", "tools", "allergies", "dietaryRestrictions")
    @classmethod
    def clean_lists(cls, value: list[str]) -> list[str]:
        return _clean(value, 20)
