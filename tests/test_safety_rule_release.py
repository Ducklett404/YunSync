from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.main import app
from app.models.audit import AuditLog
from app.models.food_safety import FoodSafetyProfile, SafetyRuleRelease
from app.models.health import HealthMetric, HealthReport
from app.services.identity_service import CURRENT_CONSENT_VERSION
from app.services.safety_rule_service import REQUIRED_SAFETY_RULE_CODES


def _login(client: TestClient, account_id: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/demo", json={"account_id": account_id})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _prepare_participant(client: TestClient) -> dict[str, str]:
    headers = _login(client, "demo-student")
    consent = client.post(
        "/api/v1/consents/accept",
        json={"version": CURRENT_CONSENT_VERSION},
        headers=headers,
    )
    assert consent.status_code == 200
    screening = client.post(
        "/api/v1/profile/screening",
        json={
            "acute_symptoms": False,
            "clinician_restriction": False,
            "recent_discomfort": False,
            "support_needed": False,
        },
        headers=headers,
    )
    assert screening.status_code == 200
    profile = client.patch(
        "/api/v1/profile/food-safety",
        json={
            "allergy_status": "none",
            "medication_status": "none",
            "condition_status": "none",
            "liver_kidney_status": "none",
            "clinician_restriction_status": "none",
            "special_status": "none",
        },
        headers=headers,
    )
    assert profile.status_code == 200
    return headers


def _reset_state() -> None:
    with SessionLocal() as db:
        db.execute(delete(SafetyRuleRelease))
        db.execute(delete(FoodSafetyProfile).where(FoodSafetyProfile.user_id == "demo-user"))
        db.commit()


def _release_payload(**overrides) -> dict:
    payload = {
        "version": "safety-review-2026-01",
        "evidence_ref": "review-record://synthetic-test-only",
        "reviewer_qualification": "测试环境专业审核角色",
        "reviewed_rule_codes": sorted(REQUIRED_SAFETY_RULE_CODES),
        "attested": True,
    }
    payload.update(overrides)
    return payload


def test_release_requires_reviewer_and_complete_attested_scope():
    with TestClient(app) as client:
        _reset_state()
        participant_headers = _prepare_participant(client)
        reviewer_headers = _login(client, "demo-reviewer")

        forbidden = client.post(
            "/api/v1/admin/safety-rules",
            json=_release_payload(),
            headers=participant_headers,
        )
        incomplete = client.post(
            "/api/v1/admin/safety-rules",
            json=_release_payload(reviewed_rule_codes=["acute_symptoms"]),
            headers=reviewer_headers,
        )
        unattested = client.post(
            "/api/v1/admin/safety-rules",
            json=_release_payload(attested=False),
            headers=reviewer_headers,
        )

    assert forbidden.status_code == 403
    assert incomplete.status_code == 409
    assert unattested.status_code == 422


def test_published_release_opens_a_tier_and_retirement_closes_it():
    report_id = str(uuid4())
    metric_id = str(uuid4())
    release_id = None
    with TestClient(app) as client:
        _reset_state()
        participant_headers = _prepare_participant(client)
        reviewer_headers = _login(client, "demo-reviewer")
        with SessionLocal() as db:
            db.add(
                HealthReport(
                    id=report_id,
                    user_id="demo-user",
                    filename="安全规则合成报告.pdf",
                    source="synthetic",
                    status="confirmed",
                    critical_marker_status="no",
                    created_at=datetime.now(timezone.utc) + timedelta(days=7),
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
                    value=22.5,
                    unit="kg/m²",
                    reference_range="18.5-23.9",
                    confirmed=True,
                    review_status="confirmed",
                )
            )
            db.commit()

        before = client.get("/api/v1/safety/decision", headers=participant_headers)
        published = client.post(
            "/api/v1/admin/safety-rules",
            json=_release_payload(),
            headers=reviewer_headers,
        )
        assert published.status_code == 200, published.text
        release_id = published.json()["id"]
        ready = client.get("/api/v1/safety/decision", headers=participant_headers)
        replacement = client.post(
            "/api/v1/admin/safety-rules",
            json=_release_payload(version="safety-review-2026-02"),
            headers=reviewer_headers,
        )
        assert replacement.status_code == 200, replacement.text
        release_id = replacement.json()["id"]
        releases = client.get("/api/v1/admin/safety-rules", headers=reviewer_headers)
        replaced_ready = client.get("/api/v1/safety/decision", headers=participant_headers)
        retired = client.patch(
            f"/api/v1/admin/safety-rules/{release_id}/retire",
            headers=reviewer_headers,
        )
        after = client.get("/api/v1/safety/decision", headers=participant_headers)

    with SessionLocal() as db:
        published_audit = db.scalar(
            select(AuditLog)
            .where(AuditLog.event_type == "safety_rule_release.published")
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        assert published_audit is not None
        assert published_audit.payload["release_id"] == release_id
        assert "测试环境专业审核角色" not in str(published_audit.payload)
        db.execute(delete(HealthMetric).where(HealthMetric.id == metric_id))
        db.execute(delete(HealthReport).where(HealthReport.id == report_id))
        db.execute(delete(SafetyRuleRelease))
        db.execute(delete(FoodSafetyProfile).where(FoodSafetyProfile.user_id == "demo-user"))
        db.commit()

    assert before.status_code == 200
    assert before.json()["decision"] == "awaiting_review_rules"
    assert ready.status_code == 200
    assert ready.json()["decision"] == "ready_general_guidance"
    assert ready.json()["tier"] == "A"
    assert ready.json()["can_generate_plan"] is True
    assert ready.json()["rule_version"].endswith("+safety-review-2026-01")
    assert releases.status_code == 200
    assert {item["version"]: item["status"] for item in releases.json()} == {
        "safety-review-2026-01": "retired",
        "safety-review-2026-02": "published",
    }
    assert replaced_ready.json()["rule_version"].endswith("+safety-review-2026-02")
    assert retired.status_code == 200
    assert retired.json()["status"] == "retired"
    assert after.json()["decision"] == "awaiting_review_rules"
    assert after.json()["can_generate_plan"] is False
