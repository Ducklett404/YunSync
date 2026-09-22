"""Three synthetic M5 cases and fail-closed plan state transitions."""

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.db.session import get_db
from app.core.security import require_active_participant
from app.main import app
from app.models import (
    CarePlan, ContentReview, EvidenceSource, FoodSafetyProfile, HealthMetric,
    HealthReport, KnowledgeItem, SafetyRuleRelease, UserProfile,
)
from app.schemas.care_plan import CarePlanRequest
from app.services.care_plan_service import CarePlanConflict, care_plan_service
from app.services.safety_rule_service import REQUIRED_SAFETY_RULE_CODES


SOURCE = "qa-approved@1"


def _item(kind: str, code: str, payload: dict) -> KnowledgeItem:
    return KnowledgeItem(
        id=f"qa-{kind}-{code}", content_type=kind, code=code, version="1",
        title=f"测试{code}", payload=payload, status="published", is_active=True,
        created_by="professional-qa", published_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def case_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = UserProfile(
            id="m5-user", role="participant", screening_status="eligible",
            screening_answers={"acute_symptoms": False}, high_risk=False,
        )
        db.add(user)
        db.add(FoodSafetyProfile(
            user_id=user.id, allergy_status="none", allergens=[],
            medication_status="none", medications=[], condition_status="none", conditions=[],
            liver_kidney_status="none", liver_kidney_conditions=[],
            clinician_restriction_status="none", clinician_restrictions=[],
            special_status="none", special_details="",
        ))
        db.add(SafetyRuleRelease(
            id="qa-release", version="qa-1", status="published", evidence_ref="qa/safety",
            reviewer_qualification="测试审核角色", reviewed_rule_codes=sorted(REQUIRED_SAFETY_RULE_CODES),
            attested=True, reviewer_id="professional-qa", published_at=datetime.now(timezone.utc),
        ))
        report = HealthReport(
            id="qa-report", user_id=user.id, filename="合成案例", status="confirmed",
            critical_marker_status="no", created_at=datetime.now(timezone.utc),
        )
        db.add(report)
        for code, name, value, unit in (
            ("bmi", "身体质量指数", 25.1, "kg/m²"),
            ("fasting_glucose", "空腹血糖", 6.1, "mmol/L"),
            ("triglyceride", "甘油三酯", 1.8, "mmol/L"),
        ):
            db.add(HealthMetric(
                id=f"qa-metric-{code}", report_id=report.id, user_id=user.id,
                code=code, name=name, value=value, unit=unit,
                reference_range="请核对原件", flag="attention", confirmed=True,
            ))
        db.add(EvidenceSource(
            id="qa-source", code="qa-approved", version="1", title="测试用批准来源",
            publisher="测试审核组", url_or_archive_ref="qa-archive/approved-source",
            published_on=date.today(), jurisdiction="测试环境", content_hash="a" * 64,
            status="active", checked_at=datetime.now(timezone.utc),
        ))
        ingredients = {
            "grain": ("测试谷物", []), "fruit": ("测试水果", []),
            "replacement": ("测试替代谷物", []), "water": ("饮用水", []),
        }
        for code, (title, allergens) in ingredients.items():
            item = _item("ingredient", code, {
                "aliases": [], "latin_species": "Test species", "edible_part": "可食部",
                "category": "ordinary_food", "processing_methods": ["清洗"],
                "allergens": allergens, "contraindication_codes": [],
                "catalog_status": "ordinary_food", "catalog_ref": "测试归档",
                "source_refs": [SOURCE],
            })
            item.title = title
            db.add(item)
            db.add(ContentReview(
                id=f"review-{item.id}", item_id=item.id, decision="approved",
                reviewer_id="professional-qa", reviewer_qualification="测试审核角色",
                review_scope="结构化测试", evidence_ref="qa/review",
                attested=True, notes="", created_at=datetime.now(timezone.utc),
            ))
        for index in range(3):
            item = _item("recipe", f"meal_{index + 1}", {
                "servings": 2,
                "goal_statement": "使用经审核的合成日常餐食模板。",
                "target_tags": ["基本信息", "血糖", "血脂"],
                "materials": [
                    {"code": "grain", "version": "1", "grams": 60 + index * 10,
                     "edible_part": "可食部", "preparation": "清洗称量",
                     "substitutions": [{"code": "replacement", "version": "1", "ratio": 1.2,
                                        "note": "按审核比例替换"}]},
                    {"code": "fruit", "version": "1", "grams": 100,
                     "edible_part": "可食部", "preparation": "清洗切块", "substitutions": []},
                ],
                "preprocessing": ["清洗并称量材料。"],
                "steps": [{"order": 1, "instruction": "用锅将材料充分煮熟。",
                           "duration_minutes": 20, "heat": "小火", "cookware": ["汤锅"]}],
                "frequency": "按一周安排每次一份。", "cycle": "七天后核对执行情况。",
                "max_weekly_uses": 3,
                "serving_note": "按成品实际分为两份。", "nutrition_tags": ["日常餐食"],
                "estimated_cost_yuan_per_serving": 8.0 + index,
                "taste_tags": ["清淡"], "region_tags": ["华东"],
                "dining_alternatives": ["使用经审核的同类餐食，并现场核对原料与份量。"],
                "contraindication_codes": [], "caution": "有不适时停止并咨询专业人员。",
                "source_refs": [SOURCE],
            })
            db.add(item)
            db.add(ContentReview(
                id=f"review-{item.id}", item_id=item.id, decision="approved",
                reviewer_id="professional-qa", reviewer_qualification="测试审核角色",
                review_scope="结构化测试", evidence_ref="qa/review",
                attested=True, notes="", created_at=datetime.now(timezone.utc),
            ))
        db.commit()
        yield db, user
    engine.dispose()


@pytest.mark.parametrize("metric_code", ["bmi", "fasting_glucose", "triglyceride"])
def test_three_representative_cases_generate_complete_plan(case_db, metric_code):
    db, user = case_db
    request = CarePlanRequest(
        selected_metric_codes=[metric_code], servings=2, start_on=date.today(),
        max_minutes=30, max_budget_yuan_per_serving=12,
        available_cookware=["汤锅"], preferred_taste="清淡", region="华东",
    )
    plan = care_plan_service.create(db, user, request)
    assert plan.status == "READY"
    snapshot = plan.snapshot
    assert len(snapshot["recipes"]) == 3
    assert len(snapshot["schedule"]) == 7
    assert snapshot["goals"][0]["code"] == metric_code
    assert all(recipe["materials"] and recipe["steps"] and recipe["source_refs"] for recipe in snapshot["recipes"])
    assert snapshot["recipes"][0]["materials"][0]["alternatives"][0]["grams"] == 72.0
    grain = next(item for item in snapshot["shopping_list"] if item["code"] == "grain")
    assert grain["total_grams"] == 480.0  # meal_1 x3, meal_2 x2, meal_3 x2
    assert care_plan_service.create(db, user, request).id == plan.id
    active = care_plan_service.activate(db, user, plan.id)
    assert active.status == "ACTIVE"


def test_substitution_recalculates_materials_and_shopping(case_db):
    db, user = case_db
    snapshot = care_plan_service.build_snapshot(db, user, CarePlanRequest(
        selected_metric_codes=["bmi"], servings=1,
        unavailable_ingredient_codes=["grain"],
    ))
    assert all(recipe.materials[0].code == "replacement" for recipe in snapshot.recipes)
    assert snapshot.recipes[0].materials[0].grams == 36.0
    assert "grain" not in {item.code for item in snapshot.shopping_list}
    assert next(item for item in snapshot.shopping_list if item.code == "replacement").total_grams == 288.0


def test_unapproved_or_changed_content_fails_closed(case_db):
    db, user = case_db
    for code in ("meal_1", "meal_2", "meal_3"):
        item = db.get(KnowledgeItem, f"qa-recipe-{code}")
        item.status = "draft"
        item.is_active = False
    db.commit()
    with pytest.raises(CarePlanConflict, match="不足 3 个"):
        care_plan_service.create(db, user, CarePlanRequest(selected_metric_codes=["bmi"]))


def test_active_plan_pauses_when_source_withdrawn(case_db):
    db, user = case_db
    plan = care_plan_service.create(db, user, CarePlanRequest(selected_metric_codes=["bmi"]))
    care_plan_service.activate(db, user, plan.id)
    source = db.get(EvidenceSource, "qa-source")
    source.status = "withdrawn"
    db.commit()
    assert care_plan_service.current(db, user).status == "PAUSED"


def test_high_risk_gate_precedes_recipe_search(case_db):
    db, user = case_db
    user.screening_answers = {"acute_symptoms": True}
    db.commit()
    with pytest.raises(CarePlanConflict, match="紧急"):
        care_plan_service.create(db, user, CarePlanRequest(selected_metric_codes=["bmi"]))


def test_demo_review_cannot_open_formal_plan(case_db):
    db, user = case_db
    release = db.get(SafetyRuleRelease, "qa-release")
    release.reviewer_id = "demo-reviewer"
    db.commit()
    with pytest.raises(CarePlanConflict, match="非演示专业审核"):
        care_plan_service.build_snapshot(db, user, CarePlanRequest(selected_metric_codes=["bmi"]))


def test_weekly_frequency_and_budget_are_hard_limits(case_db):
    db, user = case_db
    for code in ("meal_1", "meal_2", "meal_3"):
        item = db.get(KnowledgeItem, f"qa-recipe-{code}")
        item.payload = {**item.payload, "max_weekly_uses": 1}
    db.commit()
    with pytest.raises(CarePlanConflict, match="上限不足"):
        care_plan_service.build_snapshot(db, user, CarePlanRequest(selected_metric_codes=["bmi"]))
    with pytest.raises(CarePlanConflict, match="不足 3 个"):
        care_plan_service.build_snapshot(db, user, CarePlanRequest(
            selected_metric_codes=["bmi"], max_budget_yuan_per_serving=8,
        ))


def test_care_plan_api_contract_and_authorization(case_db):
    db, user = case_db
    with TestClient(app) as client:
        assert client.get("/api/v1/care-plans/current").status_code == 401
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[require_active_participant] = lambda: user
        try:
            assert client.get("/api/v1/care-plans/current").json() is None
            created = client.post("/api/v1/care-plans", json={
                "selected_metric_codes": ["bmi"], "servings": 2,
            })
            assert created.status_code == 201, created.text
            data = created.json()
            assert data["status"] == "READY"
            assert len(data["snapshot"]["schedule"]) == 7
            assert client.get("/api/v1/care-plans/current").json()["id"] == data["id"]
            activated = client.post(f"/api/v1/care-plans/{data['id']}/activate")
            assert activated.status_code == 200, activated.text
            assert activated.json()["status"] == "ACTIVE"
            exported = client.get(f"/api/v1/care-plans/{data['id']}/export")
            assert exported.status_code == 200
            assert exported.headers["cache-control"] == "private, no-store"
            assert exported.json()["snapshot"]["shopping_list"]
        finally:
            app.dependency_overrides.clear()
