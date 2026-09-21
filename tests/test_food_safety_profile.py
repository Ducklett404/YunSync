from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.main import app
from app.models.audit import AuditLog
from app.models.food_safety import FoodSafetyProfile
from app.models.health import HealthMetric, HealthReport
from app.services.identity_service import CURRENT_CONSENT_VERSION


def headers_for_participant(client: TestClient) -> dict[str, str]:
    login = client.post("/api/v1/auth/demo", json={"account_id": "demo-student"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    client.post(
        "/api/v1/consents/accept",
        json={"version": CURRENT_CONSENT_VERSION},
        headers=headers,
    )
    client.post(
        "/api/v1/profile/screening",
        json={
            "acute_symptoms": False,
            "clinician_restriction": False,
            "recent_discomfort": False,
            "support_needed": False,
        },
        headers=headers,
    )
    return headers


def reset_food_safety_profile() -> None:
    with SessionLocal() as db:
        db.execute(delete(FoodSafetyProfile).where(FoodSafetyProfile.user_id == "demo-user"))
        db.commit()


def all_none() -> dict:
    return {
        "allergy_status": "none",
        "medication_status": "none",
        "condition_status": "none",
        "liver_kidney_status": "none",
        "clinician_restriction_status": "none",
        "special_status": "none",
    }


def test_unanswered_food_safety_profile_is_not_treated_as_safe():
    with TestClient(app) as client:
        reset_food_safety_profile()
        headers = headers_for_participant(client)
        response = client.get("/api/v1/profile/food-safety", headers=headers)

    assert response.status_code == 200
    assert response.json()["allergy_status"] == "unknown"
    assert response.json()["readiness"] == "needs_information"
    assert response.json()["updated_at"] is None


def test_profile_requires_details_and_never_puts_them_in_audit():
    with TestClient(app) as client:
        reset_food_safety_profile()
        headers = headers_for_participant(client)
        incomplete = client.patch(
            "/api/v1/profile/food-safety",
            json={**all_none(), "allergy_status": "present"},
            headers=headers,
        )
        saved = client.patch(
            "/api/v1/profile/food-safety",
            json={**all_none(), "allergy_status": "present", "allergens": ["花生"]},
            headers=headers,
        )
        loaded = client.get("/api/v1/profile/food-safety", headers=headers)

    assert incomplete.status_code == 422
    assert saved.status_code == 200
    assert saved.json()["readiness"] == "needs_professional_review"
    assert loaded.json()["allergens"] == ["花生"]
    with SessionLocal() as db:
        audit = db.scalar(
            select(AuditLog)
            .where(AuditLog.event_type == "food_safety_profile.updated")
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        assert audit is not None
        assert "花生" not in str(audit.payload)


def test_complete_negative_answers_still_wait_for_reviewed_rules():
    with TestClient(app) as client:
        reset_food_safety_profile()
        headers = headers_for_participant(client)
        saved = client.patch("/api/v1/profile/food-safety", json=all_none(), headers=headers)
        reviewer = client.post("/api/v1/auth/demo", json={"account_id": "demo-reviewer"})
        reviewer_headers = {"Authorization": f"Bearer {reviewer.json()['access_token']}"}
        forbidden = client.get("/api/v1/profile/food-safety", headers=reviewer_headers)

    assert saved.status_code == 200
    assert saved.json()["readiness"] == "awaiting_review_rules"
    assert forbidden.status_code == 403


def test_existing_high_risk_screening_keeps_food_safety_profile_in_review():
    with TestClient(app) as client:
        reset_food_safety_profile()
        headers = headers_for_participant(client)
        client.patch("/api/v1/profile/food-safety", json=all_none(), headers=headers)
        client.post(
            "/api/v1/profile/screening",
            json={
                "acute_symptoms": True,
                "clinician_restriction": False,
                "recent_discomfort": False,
                "support_needed": False,
            },
            headers=headers,
        )
        response = client.get("/api/v1/profile/food-safety", headers=headers)

    assert response.status_code == 200
    assert response.json()["readiness"] == "needs_professional_review"


def test_safety_decision_never_treats_missing_answers_as_no_risk():
    with TestClient(app) as client:
        reset_food_safety_profile()
        headers = headers_for_participant(client)
        response = client.get("/api/v1/safety/decision", headers=headers)

    assert response.status_code == 200
    assert response.json()["decision"] == "complete_information"
    assert response.json()["tier"] is None
    assert response.json()["can_generate_plan"] is False
    assert "食物或原料过敏" in response.json()["missing_items"]


def test_safety_decision_blocks_known_risk_and_prioritizes_acute_symptoms():
    with TestClient(app) as client:
        reset_food_safety_profile()
        headers = headers_for_participant(client)
        client.patch(
            "/api/v1/profile/food-safety",
            json={**all_none(), "allergy_status": "present", "allergens": ["花生"]},
            headers=headers,
        )
        consultation = client.get("/api/v1/safety/decision", headers=headers)
        client.post(
            "/api/v1/profile/screening",
            json={
                "acute_symptoms": True,
                "clinician_restriction": False,
                "recent_discomfort": False,
                "support_needed": False,
            },
            headers=headers,
        )
        urgent = client.get("/api/v1/safety/decision", headers=headers)

    assert consultation.json()["decision"] == "consult_professional"
    assert consultation.json()["tier"] == "B"
    assert urgent.json()["decision"] == "urgent_care"
    assert urgent.json()["tier"] == "C"
    assert urgent.json()["can_generate_plan"] is False


def test_complete_report_and_profile_still_wait_for_professional_rules():
    report_id = str(uuid4())
    metric_id = str(uuid4())
    with TestClient(app) as client:
        reset_food_safety_profile()
        headers = headers_for_participant(client)
        client.patch("/api/v1/profile/food-safety", json=all_none(), headers=headers)
        with SessionLocal() as db:
            db.add(
                HealthReport(
                    id=report_id,
                    user_id="demo-user",
                    filename="合成报告.pdf",
                    source="synthetic",
                    status="needs_confirmation",
                    critical_marker_status="no",
                    created_at=datetime.now(timezone.utc) + timedelta(days=1),
                )
            )
            db.flush()
            db.add(
                HealthMetric(
                    id=metric_id,
                    report_id=report_id,
                    user_id="demo-user",
                    code="bmi",
                    name="身体质量指数",
                    value=23.0,
                    unit="kg/m²",
                    confirmed=True,
                )
            )
            db.commit()
        pending = client.get("/api/v1/safety/decision", headers=headers)
        with SessionLocal() as db:
            report = db.get(HealthReport, report_id)
            assert report is not None
            report.status = "confirmed"
            db.commit()
        response = client.get("/api/v1/safety/decision", headers=headers)
        with SessionLocal() as db:
            metric = db.get(HealthMetric, metric_id)
            assert metric is not None
            db.delete(metric)
            db.commit()
        empty_report = client.get("/api/v1/safety/decision", headers=headers)

    with SessionLocal() as db:
        report = db.get(HealthReport, report_id)
        if report:
            db.delete(report)
            db.commit()
    assert pending.json()["decision"] == "complete_information"
    assert "报告逐项确认" in pending.json()["missing_items"]
    assert response.status_code == 200
    assert response.json()["decision"] == "awaiting_review_rules"
    assert response.json()["can_generate_plan"] is False
    assert empty_report.json()["decision"] == "complete_information"


def test_user_confirmed_report_critical_marker_has_priority_without_numeric_thresholds():
    report_id = str(uuid4())
    with TestClient(app) as client:
        headers = headers_for_participant(client)
        with SessionLocal() as db:
            db.add(
                HealthReport(
                    id=report_id,
                    user_id="demo-user",
                    filename="危急标记合成报告.pdf",
                    source="synthetic",
                    status="needs_confirmation",
                    created_at=datetime.now(timezone.utc) + timedelta(days=1),
                )
            )
            db.commit()
        unknown = client.get("/api/v1/safety/decision", headers=headers)
        marked = client.patch(
            f"/api/v1/reports/{report_id}/critical-marker",
            json={"status": "yes"},
            headers=headers,
        )
        urgent = client.get("/api/v1/safety/decision", headers=headers)
        cleared = client.patch(
            f"/api/v1/reports/{report_id}/critical-marker",
            json={"status": "no"},
            headers=headers,
        )
        no_longer_urgent = client.get("/api/v1/safety/decision", headers=headers)
        invalid = client.patch(
            f"/api/v1/reports/{report_id}/critical-marker",
            json={"status": "inferred_from_value"},
            headers=headers,
        )
        missing = client.patch(
            f"/api/v1/reports/{uuid4()}/critical-marker",
            json={"status": "yes"},
            headers=headers,
        )

    with SessionLocal() as db:
        report = db.get(HealthReport, report_id)
        if report:
            db.delete(report)
            db.commit()
        audit = db.scalar(
            select(AuditLog)
            .where(AuditLog.event_type == "report.critical_marker_reviewed")
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        assert audit is not None
        assert "yes" not in str(audit.payload)
    assert unknown.json()["decision"] != "urgent_care"
    assert marked.status_code == 200
    assert marked.json()["critical_marker_status"] == "yes"
    assert marked.json()["critical_marker_reviewed_at"] is not None
    assert urgent.json()["decision"] == "urgent_care"
    assert urgent.json()["tier"] == "C"
    assert cleared.json()["critical_marker_status"] == "no"
    assert no_longer_urgent.json()["decision"] != "urgent_care"
    assert invalid.status_code == 422
    assert missing.status_code == 404
