from datetime import date, datetime
import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ContentType = Literal["ingredient", "recipe", "contraindication"]
ContentStatus = Literal["draft", "reviewed", "published", "retired"]
CODE_PATTERN = r"^[a-z0-9][a-z0-9_-]{1,63}$"
VERSION_PATTERN = r"^[0-9A-Za-z][0-9A-Za-z._-]{0,39}$"
SOURCE_REF_PATTERN = r"^[a-z0-9][a-z0-9_-]{1,63}@[0-9A-Za-z][0-9A-Za-z._-]{0,39}$"


def _clean_list(values: list[str]) -> list[str]:
    cleaned = [value.strip() for value in values]
    if any(not value for value in cleaned) or len(set(cleaned)) != len(cleaned):
        raise ValueError("列表项不能为空或重复")
    return cleaned


class EvidenceSourceIn(BaseModel):
    code: str = Field(pattern=CODE_PATTERN)
    version: str = Field(pattern=VERSION_PATTERN)
    title: str = Field(min_length=3, max_length=240)
    publisher: str = Field(min_length=2, max_length=160)
    url_or_archive_ref: str = Field(min_length=3, max_length=500)
    published_on: date
    jurisdiction: str = Field(min_length=2, max_length=80)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["active", "superseded", "withdrawn"] = "active"
    checked_at: datetime

    @field_validator("title", "publisher", "url_or_archive_ref", "jurisdiction")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()


class EvidenceSourceOut(EvidenceSourceIn):
    id: str
    ref: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EvidenceSourceStatusUpdate(BaseModel):
    status: Literal["active", "superseded", "withdrawn"]


class IngredientPayload(BaseModel):
    aliases: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list, max_length=20)
    latin_species: str = Field(min_length=2, max_length=240)
    edible_part: str = Field(min_length=1, max_length=80)
    category: Literal["ordinary_food", "food_medicine"]
    processing_methods: list[Annotated[str, Field(max_length=80)]] = Field(min_length=1, max_length=20)
    allergens: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list, max_length=20)
    contraindication_codes: list[str] = Field(default_factory=list, max_length=30)
    catalog_status: Literal["ordinary_food", "listed", "pending_verification", "retired"]
    catalog_ref: str = Field(default="", max_length=240)
    source_refs: list[str] = Field(min_length=1, max_length=20)

    @field_validator("aliases", "processing_methods", "allergens", "contraindication_codes")
    @classmethod
    def normalize_lists(cls, values: list[str]) -> list[str]:
        return _clean_list(values)

    @field_validator("source_refs")
    @classmethod
    def validate_source_refs(cls, values: list[str]) -> list[str]:
        values = _clean_list(values)
        for value in values:
            if not re.fullmatch(SOURCE_REF_PATTERN, value):
                raise ValueError("来源引用必须使用 code@version")
        return values

    @model_validator(mode="after")
    def validate_catalog_identity(self):
        if self.category == "food_medicine":
            if self.catalog_status not in {"listed", "pending_verification", "retired"}:
                raise ValueError("食药物质必须记录目录状态")
            if not self.catalog_ref.strip():
                raise ValueError("食药物质必须记录目录依据")
        elif self.catalog_status != "ordinary_food":
            raise ValueError("普通食物的目录状态必须为 ordinary_food")
        return self


class IngredientRef(BaseModel):
    code: str = Field(pattern=CODE_PATTERN)
    version: str = Field(pattern=VERSION_PATTERN)


class RecipeSubstitution(IngredientRef):
    ratio: float = Field(gt=0, le=10)
    note: str = Field(min_length=2, max_length=160)


class RecipeMaterial(IngredientRef):
    grams: float = Field(gt=0, le=3000)
    edible_part: str = Field(min_length=1, max_length=80)
    preparation: str = Field(min_length=2, max_length=240)
    substitutions: list[RecipeSubstitution] = Field(default_factory=list, max_length=8)


class RecipeStep(BaseModel):
    order: int = Field(ge=1, le=30)
    instruction: str = Field(min_length=3, max_length=500)
    duration_minutes: int = Field(ge=0, le=360)
    heat: str = Field(min_length=1, max_length=80)
    cookware: list[Annotated[str, Field(max_length=80)]] = Field(min_length=1, max_length=10)

    @field_validator("cookware")
    @classmethod
    def normalize_cookware(cls, values: list[str]) -> list[str]:
        return _clean_list(values)


class RecipePayload(BaseModel):
    servings: int = Field(ge=1, le=12)
    goal_statement: str = Field(min_length=3, max_length=240)
    target_tags: list[Annotated[str, Field(max_length=80)]] = Field(min_length=1, max_length=12)
    materials: list[RecipeMaterial] = Field(min_length=1, max_length=30)
    preprocessing: list[Annotated[str, Field(max_length=240)]] = Field(min_length=1, max_length=20)
    steps: list[RecipeStep] = Field(min_length=1, max_length=30)
    frequency: str = Field(min_length=2, max_length=160)
    cycle: str = Field(min_length=2, max_length=160)
    serving_note: str = Field(min_length=3, max_length=240)
    nutrition_tags: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list, max_length=20)
    contraindication_codes: list[str] = Field(default_factory=list, max_length=30)
    caution: str = Field(min_length=3, max_length=500)
    source_refs: list[str] = Field(min_length=1, max_length=20)

    @field_validator(
        "target_tags",
        "preprocessing",
        "nutrition_tags",
        "contraindication_codes",
    )
    @classmethod
    def normalize_lists(cls, values: list[str]) -> list[str]:
        return _clean_list(values)

    @field_validator("source_refs")
    @classmethod
    def validate_source_refs(cls, values: list[str]) -> list[str]:
        values = _clean_list(values)
        for value in values:
            if not re.fullmatch(SOURCE_REF_PATTERN, value):
                raise ValueError("来源引用必须使用 code@version")
        return values

    @model_validator(mode="after")
    def validate_steps_and_materials(self):
        orders = [step.order for step in self.steps]
        if sorted(orders) != list(range(1, len(orders) + 1)):
            raise ValueError("制作步骤序号必须从 1 连续递增")
        refs = [(item.code, item.version) for item in self.materials]
        if len(refs) != len(set(refs)):
            raise ValueError("同一食谱不能重复列出相同版本的材料")
        return self


class ContraindicationPayload(BaseModel):
    subject_type: Literal["ingredient", "recipe"]
    subject_code: str = Field(pattern=CODE_PATTERN)
    trigger_type: Literal[
        "allergy",
        "medication",
        "condition",
        "liver_kidney",
        "pregnancy",
        "breastfeeding",
        "clinician_restriction",
        "missing_information",
    ]
    trigger_values: list[Annotated[str, Field(max_length=80)]] = Field(min_length=1, max_length=30)
    action: Literal["block", "professional_review", "warn"]
    message: str = Field(min_length=3, max_length=500)
    source_refs: list[str] = Field(min_length=1, max_length=20)

    @field_validator("trigger_values")
    @classmethod
    def normalize_lists(cls, values: list[str]) -> list[str]:
        return _clean_list(values)

    @field_validator("source_refs")
    @classmethod
    def validate_source_refs(cls, values: list[str]) -> list[str]:
        values = _clean_list(values)
        for value in values:
            if not re.fullmatch(SOURCE_REF_PATTERN, value):
                raise ValueError("来源引用必须使用 code@version")
        return values


PayloadModel = IngredientPayload | RecipePayload | ContraindicationPayload


def parse_content_payload(content_type: ContentType, payload: dict) -> PayloadModel:
    model = {
        "ingredient": IngredientPayload,
        "recipe": RecipePayload,
        "contraindication": ContraindicationPayload,
    }[content_type]
    return model.model_validate(payload)


class ContentItemCreate(BaseModel):
    content_type: ContentType
    code: str = Field(pattern=CODE_PATTERN)
    version: str = Field(pattern=VERSION_PATTERN)
    title: str = Field(min_length=2, max_length=160)
    payload: dict

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_payload(self):
        self.payload = parse_content_payload(self.content_type, self.payload).model_dump(mode="json")
        return self


class ContentItemOut(BaseModel):
    id: str
    content_type: ContentType
    code: str
    version: str
    title: str
    payload: dict
    status: ContentStatus
    is_active: bool
    created_by: str
    created_at: datetime
    published_at: datetime | None
    retired_at: datetime | None

    model_config = {"from_attributes": True}


class ContentReviewIn(BaseModel):
    decision: Literal["approved", "rejected"]
    reviewer_qualification: str = Field(min_length=3, max_length=160)
    review_scope: str = Field(min_length=3, max_length=240)
    evidence_ref: str = Field(min_length=3, max_length=240)
    attested: Literal[True]
    notes: str = Field(default="", max_length=1000)

    @field_validator("reviewer_qualification", "review_scope", "evidence_ref", "notes")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()


class ContentReviewOut(BaseModel):
    id: str
    item_id: str
    decision: Literal["approved", "rejected"]
    reviewer_id: str
    reviewer_qualification: str
    review_scope: str
    evidence_ref: str
    attested: bool
    notes: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ContentCompareOut(BaseModel):
    content_type: ContentType
    code: str
    from_version: str
    to_version: str
    changed_fields: dict[str, dict[str, object | None]]


class BulkValidationIn(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("item_ids")
    @classmethod
    def unique_ids(cls, values: list[str]) -> list[str]:
        return _clean_list(values)


class ContentValidationResult(BaseModel):
    item_id: str
    content_type: ContentType | None
    code: str | None
    version: str | None
    valid: bool
    errors: list[str]
    warnings: list[str]


class BulkValidationOut(BaseModel):
    valid: bool
    results: list[ContentValidationResult]


class CatalogItemOut(BaseModel):
    code: str
    version: str
    title: str
    payload: dict
    published_at: datetime
