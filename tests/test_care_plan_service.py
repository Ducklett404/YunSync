"""Three synthetic M5 cases and fail-closed plan state transitions."""

from datetime import date, datetime, timedelta, timezone

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
    AuditLog, CarePlan, ContentReview, EvidenceSource, FoodSafetyProfile, HealthMetric,
    HealthReport, KnowledgeItem, SafetyRuleRelease, UserProfile,
)
from app.schemas.care_plan import AdherenceLogIn, CarePlanRequest, ReminderIn
from app.services.care_plan_service import CarePlanConflict, care_plan_service
from app.services.care_plan_follow_up_service import (
    get_revision, record_log, revise_plan, set_reminder,
)
from app.services.follow_up_service import compare_reports
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
            assert exported.json()["format"] == "yunsync-care-plan-v2"
            assert exported.json()["version"] == 1
            assert exported.json()["snapshot"]["shopping_list"]
        finally:
            app.dependency_overrides.clear()


def _add_follow_up_report(db: Session, user: UserProfile, *, confirmed: bool = True):
    old = db.get(HealthReport, "qa-report")
    old.examined_at = datetime.now(timezone.utc) - timedelta(days=8)
    old.institution = "测试机构"
    for metric in db.query(HealthMetric).filter(HealthMetric.report_id == old.id):
        metric.method = "测试方法"
    new = HealthReport(
        id="qa-report-follow-up", user_id=user.id, filename="合成复查报告",
        status="confirmed" if confirmed else "needs_confirmation",
        critical_marker_status="no", institution="测试机构",
        examined_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc) + timedelta(seconds=1),
    )
    db.add(new)
    for code, name, value, unit in (
        ("bmi", "身体质量指数", 24.8, "kg/m²"),
        ("fasting_glucose", "空腹血糖", 5.9, "mmol/L"),
        ("triglyceride", "甘油三酯", 1.7, "mmol/L"),
    ):
        db.add(HealthMetric(
            id=f"qa-follow-up-{code}", report_id=new.id, user_id=user.id,
            code=code, name=name, value=value, unit=unit,
            reference_range="请核对原件", method="测试方法",
            flag="attention", confirmed=confirmed,
        ))
    db.commit()
    return new


def test_m6_feedback_is_idempotent_and_discomfort_pauses(case_db):
    db, user = case_db
    plan = care_plan_service.create(db, user, CarePlanRequest(selected_metric_codes=["bmi"]))
    care_plan_service.activate(db, user, plan.id)
    payload = AdherenceLogIn(status="completed", note="测试完成")
    first = record_log(db, user, plan.id, 1, payload)
    again = record_log(db, user, plan.id, 1, payload)
    assert first.id == again.id
    with pytest.raises(CarePlanConflict, match="未来日期"):
        record_log(db, user, plan.id, 7, payload)
    adverse_payload = AdherenceLogIn(
        status="replaced", replacement="自行选择的其他食物", discomfort=True, note="测试不适",
    )
    adverse = record_log(db, user, plan.id, 1, adverse_payload)
    assert adverse.discomfort is True
    assert db.get(CarePlan, plan.id).status == "PAUSED"
    assert db.get(CarePlan, plan.id).pause_reason == "adverse_feedback"
    feedback_events = db.query(AuditLog).filter(AuditLog.event_type == "care_plan.feedback").all()
    assert feedback_events
    assert all("note" not in event.payload and "replacement" not in event.payload
               for event in feedback_events)
    assert record_log(db, user, plan.id, 1, adverse_payload).id == adverse.id
    with pytest.raises(CarePlanConflict, match="专业评估"):
        care_plan_service.create(db, user, CarePlanRequest(selected_metric_codes=["bmi"]))


def test_m6_reminder_uses_explicit_basis_and_does_not_infer_period(case_db):
    db, user = case_db
    plan = care_plan_service.create(db, user, CarePlanRequest(selected_metric_codes=["bmi"]))
    future = date.today() + timedelta(days=60)
    payload = ReminderIn(remind_on=future, basis="personal", note="既定体检计划")
    first = set_reminder(db, user, plan.id, payload)
    assert set_reminder(db, user, plan.id, payload).id == first.id
    assert first.remind_on == future
    with pytest.raises(CarePlanConflict, match="依据"):
        set_reminder(db, user, plan.id, ReminderIn(remind_on=future, basis="doctor"))


def test_m6_two_reports_to_revision_and_superseded_snapshot(case_db):
    db, user = case_db
    old = care_plan_service.create(db, user, CarePlanRequest(selected_metric_codes=["bmi"]))
    care_plan_service.activate(db, user, old.id)
    record_log(db, user, old.id, 1, AdherenceLogIn(status="completed", note="按计划完成"))
    _add_follow_up_report(db, user)
    comparison = compare_reports(db, user.id, old.report_id, "qa-report-follow-up")
    bmi = next(item for item in comparison.metrics if item.code == "bmi")
    assert comparison.days_between == 8
    assert bmi.pair is not None and bmi.pair.status == "numeric_only"
    assert bmi.pair.arithmetic_change == pytest.approx(-0.3)
    assert "不代表健康改善" in bmi.pair.limitations[0]
    assert care_plan_service.current(db, user).pause_reason == "new_report"
    with pytest.raises(CarePlanConflict, match="复查修订"):
        care_plan_service.create(db, user, CarePlanRequest(selected_metric_codes=["bmi"]))
    new = revise_plan(db, user, old.id, CarePlanRequest(selected_metric_codes=["bmi"]))
    assert new.status == "READY" and new.version == 2
    assert new.previous_plan_id == old.id
    assert revise_plan(db, user, old.id, CarePlanRequest(selected_metric_codes=["bmi"])).id == new.id
    revision = get_revision(db, user, new.id)
    assert revision is not None and revision.changes
    assert revision.comparison["previous_report_id"] == old.report_id
    assert revision.comparison["adherence_summary"]["completed_days"] == 1
    assert revision.changes[0]["subject"] == "旧方案执行背景"
    care_plan_service.activate(db, user, new.id)
    db.refresh(old)
    assert old.status == "SUPERSEDED"
    assert old.snapshot["report_id"] == "qa-report"
    assert new.snapshot["report_id"] == "qa-report-follow-up"


def test_m6_unconfirmed_or_incomparable_reports_cannot_claim_change(case_db):
    db, user = case_db
    old = care_plan_service.create(db, user, CarePlanRequest(selected_metric_codes=["bmi"]))
    care_plan_service.activate(db, user, old.id)
    new_report = _add_follow_up_report(db, user, confirmed=False)
    with pytest.raises(RuntimeError, match="整份核对"):
        compare_reports(db, user.id, old.report_id, new_report.id)
    with pytest.raises(CarePlanConflict, match="整份核对"):
        revise_plan(db, user, old.id, CarePlanRequest(selected_metric_codes=["bmi"]))
    new_report.status = "confirmed"
    for metric in db.query(HealthMetric).filter(HealthMetric.report_id == new_report.id):
        metric.confirmed = True
        metric.method = "不同方法"
    new_report.created_at = db.get(HealthReport, old.report_id).created_at - timedelta(days=1)
    db.commit()
    comparison = compare_reports(db, user.id, old.report_id, new_report.id)
    assert all(item.pair and item.pair.arithmetic_change is None for item in comparison.metrics)
    assert all(item.pair and item.pair.status == "method_changed" for item in comparison.metrics)


def test_m6_revision_returns_business_conflict_for_reverse_examined_dates(case_db):
    db, user = case_db
    old = care_plan_service.create(db, user, CarePlanRequest(selected_metric_codes=["bmi"]))
    care_plan_service.activate(db, user, old.id)
    current_report = _add_follow_up_report(db, user)
    previous_report = db.get(HealthReport, old.report_id)
    current_report.examined_at = previous_report.examined_at - timedelta(days=1)
    db.commit()

    with TestClient(app) as client:
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[require_active_participant] = lambda: user
        try:
            response = client.post(
                f"/api/v1/care-plans/{old.id}/revise",
                json={"selected_metric_codes": ["bmi"]},
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 409
    assert "检查日期不能早于" in response.json()["detail"]


def test_m6_new_report_invalidates_unconfirmed_plan_draft(case_db):
    db, user = case_db
    old = care_plan_service.create(db, user, CarePlanRequest(selected_metric_codes=["bmi"]))
    assert old.status == "READY"
    _add_follow_up_report(db, user)
    assert care_plan_service.current(db, user).pause_reason == "new_report"
    revised = revise_plan(db, user, old.id, CarePlanRequest(selected_metric_codes=["bmi"]))
    assert revised.version == 2
    care_plan_service.activate(db, user, revised.id)
    db.refresh(old)
    assert old.status == "SUPERSEDED"


def test_m6_api_owner_scope_and_revision_contract(case_db):
    db, user = case_db
    first_report = db.get(HealthReport, "qa-report")
    first_report.examined_at = datetime.now(timezone.utc) - timedelta(days=8)
    first_report.institution = "测试机构"
    for metric in db.query(HealthMetric).filter(HealthMetric.report_id == first_report.id):
        metric.method = "测试方法"
    db.commit()
    with TestClient(app) as client:
        preflight = client.options(
            "/api/v1/care-plans/example/reminder",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "PUT",
            },
        )
        assert preflight.status_code == 200
        assert "PUT" in preflight.headers["access-control-allow-methods"]
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[require_active_participant] = lambda: user
        try:
            created = client.post("/api/v1/care-plans", json={"selected_metric_codes": ["bmi"]})
            assert created.status_code == 201, created.text
            plan_id = created.json()["id"]
            assert client.post(f"/api/v1/care-plans/{plan_id}/activate").status_code == 200
            feedback = client.put(f"/api/v1/care-plans/{plan_id}/logs/1", json={"status": "completed"})
            assert feedback.status_code == 200, feedback.text
            assert len(client.get(f"/api/v1/care-plans/{plan_id}/logs").json()) == 1
            reminder = client.put(f"/api/v1/care-plans/{plan_id}/reminder", json={
                "remind_on": (date.today() + timedelta(days=20)).isoformat(),
                "basis": "personal", "note": "既定计划", "enabled": True,
            })
            assert reminder.status_code == 200, reminder.text
            manual = client.post("/api/v1/reports/manual", json={
                "title": "合成复查报告", "institution": "测试机构",
                "measured_at": datetime.now(timezone.utc).isoformat(),
                "metrics": [{
                    "name": "身体质量指数", "value": 24.8, "unit": "kg/m²",
                    "reference_range": "请核对原件", "method": "测试方法",
                }],
            })
            assert manual.status_code == 200, manual.text
            new_report_id = manual.json()["report_id"]
            assert client.post(
                f"/api/v1/reports/{new_report_id}/metrics/{manual.json()['metrics'][0]['id']}/confirm"
            ).status_code == 200
            assert client.patch(
                f"/api/v1/reports/{new_report_id}/critical-marker", json={"status": "no"}
            ).status_code == 200
            assert client.post(f"/api/v1/reports/{new_report_id}/confirm").status_code == 200
            compared = client.post("/api/v1/follow-ups/compare", json={
                "previous_report_id": "qa-report", "current_report_id": new_report_id,
            })
            assert compared.status_code == 200, compared.text
            compared_bmi = next(item for item in compared.json()["metrics"] if item["code"] == "bmi")
            assert compared_bmi["pair"]["status"] == "numeric_only"
            revised = client.post(f"/api/v1/care-plans/{plan_id}/revise", json={
                "selected_metric_codes": ["bmi"],
            })
            assert revised.status_code == 201, revised.text
            assert revised.json()["version"] == 2
            assert client.get(f"/api/v1/care-plans/{revised.json()['id']}/revision").json()["changes"]
            outsider = UserProfile(id="outsider", role="participant", screening_status="eligible")
            db.add(outsider)
            db.commit()
            app.dependency_overrides[require_active_participant] = lambda: outsider
            assert client.get(f"/api/v1/care-plans/{plan_id}/logs").status_code == 404
            assert client.get(f"/api/v1/care-plans/{plan_id}/revision").status_code == 404
            assert client.post("/api/v1/follow-ups/compare", json={
                "previous_report_id": "qa-report", "current_report_id": new_report_id,
            }).status_code == 404
        finally:
            app.dependency_overrides.clear()
