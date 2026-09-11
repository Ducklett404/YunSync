from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.main import app
from app.models.experiment import Experiment
from app.models.identity import AuthSession, ConsentRecord
from app.services.identity_service import CURRENT_CONSENT_VERSION, hash_session_token


SAFE_SCREENING = {
    "acute_symptoms": False,
    "clinician_restriction": False,
    "recent_discomfort": False,
    "support_needed": False,
}


def login_demo(client: TestClient, account_id: str = "demo-student") -> dict[str, str]:
    response = client.post("/api/v1/auth/demo", json={"account_id": account_id})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def authorize_demo(client: TestClient) -> dict[str, str]:
    headers = login_demo(client)
    consent = client.post(
        "/api/v1/consents/accept",
        json={"version": CURRENT_CONSENT_VERSION},
        headers=headers,
    )
    assert consent.status_code == 200
    screening = client.post(
        "/api/v1/profile/screening", json=SAFE_SCREENING, headers=headers
    )
    assert screening.status_code == 200
    assert screening.json()["screening_status"] == "eligible"
    return headers


def test_health_and_readiness_endpoints():
    with TestClient(app) as client:
        health = client.get("/healthz")
        ready = client.get("/readyz")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_request_id_is_returned_and_invalid_value_is_replaced():
    with TestClient(app) as client:
        accepted = client.get("/healthz", headers={"X-Request-ID": "test-request-123"})
        replaced = client.get("/healthz", headers={"X-Request-ID": "invalid request id"})
        missing = client.get("/api/v1/route-that-does-not-exist")

    assert accepted.headers["X-Request-ID"] == "test-request-123"
    assert replaced.headers["X-Request-ID"] != "invalid request id"
    assert len(replaced.headers["X-Request-ID"]) == 32
    assert missing.status_code == 404
    assert len(missing.headers["X-Request-ID"]) == 32


def test_demo_dashboard_contains_complete_flow():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        response = client.get("/api/v1/dashboard", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["report"]["source"] == "synthetic"
    assert len(payload["metrics"]) >= 5
    assert len(payload["actions"]) == 3
    assert payload["experiment"]["progress"] >= 5


def test_report_rejects_unsupported_file_type():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        response = client.post(
            "/api/v1/reports/analyze",
            files={"file": ("notes.txt", b"not a report", "text/plain")},
            headers=headers,
        )

    assert response.status_code == 400


def test_observation_cannot_override_randomized_condition():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        experiment = client.get("/api/v1/experiments/current", headers=headers).json()
        day = next(item for item in experiment["schedule"] if item["date"] <= date.today().isoformat())
        response = client.post(
            f"/api/v1/experiments/{experiment['id']}/observations",
            json={
                "observed_on": day["date"],
                "treatment": not day["treatment"],
                "completed": True,
                "steps_30m": 1200,
            },
            headers=headers,
        )

    assert response.status_code == 400
    assert "随机日程不一致" in response.json()["detail"]


def test_future_observation_is_rejected():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        experiment = client.get("/api/v1/experiments/current", headers=headers).json()
        day = next(item for item in experiment["schedule"] if item["date"] > date.today().isoformat())
        response = client.post(
            f"/api/v1/experiments/{experiment['id']}/observations",
            json={"observed_on": day["date"], "completed": True, "steps_30m": 1200},
            headers=headers,
        )

    assert response.status_code == 400
    assert "未来日期" in response.json()["detail"]


def test_drink_experiment_uses_drink_count_as_result_metric():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        created = client.post(
            "/api/v1/experiments",
            json={
                "action_id": "action-drink-swap",
                "start_date": (date.today() - timedelta(days=13)).isoformat(),
            },
            headers=headers,
        )
        assert created.status_code == 200
        experiment = created.json()
        treatment_days = [item for item in experiment["schedule"] if item["treatment"]][:2]
        control_days = [item for item in experiment["schedule"] if not item["treatment"]][:2]

        for day, value in zip(treatment_days + control_days, [0, 1, 2, 3]):
            response = client.post(
                f"/api/v1/experiments/{experiment['id']}/observations",
                json={
                    "observed_on": day["date"],
                    "completed": True,
                    "sugary_drinks": value,
                },
                headers=headers,
            )
            assert response.status_code == 200

        result = client.get(
            f"/api/v1/experiments/{experiment['id']}/result", headers=headers
        )

    assert result.status_code == 200
    assert result.json()["metric_code"] == "sugary_drinks"
    assert result.json()["metric_unit"] == "次"
    assert result.json()["treatment_average"] == 0.5
    assert result.json()["control_average"] == 2.5


def test_health_endpoints_require_login_and_current_consent():
    with TestClient(app) as client:
        anonymous = client.post(
            "/api/v1/reports/analyze",
            files={"file": ("synthetic.pdf", b"%PDF synthetic", "application/pdf")},
        )
        headers = login_demo(client)
        client.post("/api/v1/consents/withdraw", headers=headers)
        without_consent = client.post(
            "/api/v1/reports/analyze",
            files={"file": ("synthetic.pdf", b"%PDF synthetic", "application/pdf")},
            headers=headers,
        )

    assert anonymous.status_code == 401
    assert without_consent.status_code == 403
    assert "知情说明" in without_consent.json()["detail"]


def test_profile_roles_and_minimal_audit_events():
    with TestClient(app) as client:
        participant_headers = authorize_demo(client)
        updated = client.patch(
            "/api/v1/profile",
            json={
                "goal": "验证合成档案更新",
                "sleep_schedule": "合成作息：23:00 至 07:00",
                "preferences": "每日记录不超过一分钟",
            },
            headers=participant_headers,
        )
        participant_audit = client.get(
            "/api/v1/admin/audit-events", headers=participant_headers
        )

        reviewer_headers = login_demo(client, "demo-reviewer")
        reviewer_audit = client.get(
            "/api/v1/admin/audit-events", headers=reviewer_headers
        )
        reviewer_health = client.get("/api/v1/dashboard", headers=reviewer_headers)

    assert updated.status_code == 200
    assert updated.json()["goal"] == "验证合成档案更新"
    assert participant_audit.status_code == 403
    assert reviewer_audit.status_code == 200
    profile_event = next(
        item for item in reviewer_audit.json() if item["event_type"] == "profile.updated"
    )
    assert profile_event["payload"] == {
        "changed_fields": ["goal", "preferences", "sleep_schedule"]
    }
    assert reviewer_health.status_code == 403


def test_raw_session_token_is_not_stored_and_consent_is_idempotent():
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/demo", json={"account_id": "demo-student"}
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        stale = client.post(
            "/api/v1/consents/accept",
            json={"version": "obsolete-version"},
            headers=headers,
        )
        first = client.post(
            "/api/v1/consents/accept",
            json={"version": CURRENT_CONSENT_VERSION},
            headers=headers,
        )
        second = client.post(
            "/api/v1/consents/accept",
            json={"version": CURRENT_CONSENT_VERSION},
            headers=headers,
        )

    with SessionLocal() as db:
        stored_session = db.scalar(
            select(AuthSession)
            .where(AuthSession.user_id == "demo-user")
            .order_by(AuthSession.created_at.desc())
            .limit(1)
        )
        active_count = db.scalar(
            select(func.count())
            .select_from(ConsentRecord)
            .where(
                ConsentRecord.user_id == "demo-user",
                ConsentRecord.status == "active",
            )
        )

    assert stale.status_code == 409
    assert first.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert stored_session is not None
    assert stored_session.token_hash == hash_session_token(token)
    assert stored_session.token_hash != token
    assert active_count == 1


def test_report_audit_does_not_store_uploaded_filename():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        analyzed = client.post(
            "/api/v1/reports/analyze",
            files={
                "file": (
                    "should-not-appear-in-audit.pdf",
                    b"%PDF synthetic",
                    "application/pdf",
                )
            },
            headers=headers,
        )
        assert analyzed.status_code == 200
        report_payload = analyzed.json()
        for metric in report_payload["metrics"]:
            confirmed = client.post(
                f"/api/v1/reports/{report_payload['report_id']}/metrics/{metric['id']}/confirm",
                headers=headers,
            )
            assert confirmed.status_code == 200
        finalized = client.post(
            f"/api/v1/reports/{report_payload['report_id']}/confirm", headers=headers
        )
        assert finalized.status_code == 200
        reviewer_headers = login_demo(client, "demo-reviewer")
        audit = client.get("/api/v1/admin/audit-events", headers=reviewer_headers)

    assert audit.status_code == 200
    assert "should-not-appear-in-audit.pdf" not in audit.text


def test_high_risk_screening_blocks_self_service_experiment():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        high_risk = client.post(
            "/api/v1/profile/screening",
            json={**SAFE_SCREENING, "acute_symptoms": True},
            headers=headers,
        )
        actions = client.get("/api/v1/actions", headers=headers)
        experiment = client.post(
            "/api/v1/experiments",
            json={"action_id": "action-postmeal-walk"},
            headers=headers,
        )
        client.post("/api/v1/profile/screening", json=SAFE_SCREENING, headers=headers)

    assert high_risk.status_code == 200
    assert high_risk.json()["screening_status"] == "needs_professional_review"
    assert actions.status_code == 409
    assert experiment.status_code == 409


def test_withdrawal_stops_new_analysis_and_pauses_active_experiment():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        created = client.post(
            "/api/v1/experiments",
            json={"action_id": "action-postmeal-walk"},
            headers=headers,
        )
        assert created.status_code == 200

        withdrawn = client.post("/api/v1/consents/withdraw", headers=headers)
        blocked = client.post(
            "/api/v1/reports/analyze",
            files={"file": ("synthetic.pdf", b"%PDF synthetic", "application/pdf")},
            headers=headers,
        )
        status = client.get("/api/v1/account/status", headers=headers)

    with SessionLocal() as db:
        stored_experiment = db.get(Experiment, created.json()["id"])
        experiment_status = stored_experiment.status if stored_experiment else None

    assert withdrawn.status_code == 200
    assert blocked.status_code == 403
    assert status.status_code == 200
    assert status.json()["consent"] is None
    assert experiment_status == "paused"


def test_logout_revokes_demo_session():
    with TestClient(app) as client:
        headers = login_demo(client)
        logged_out = client.post("/api/v1/auth/logout", headers=headers)
        rejected = client.get("/api/v1/auth/me", headers=headers)

    assert logged_out.status_code == 200
    assert rejected.status_code == 401


def test_report_requires_magic_signature_and_sanitizes_filename():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        mismatched = client.post(
            "/api/v1/reports/analyze",
            files={"file": ("fake.pdf", b"not-a-pdf", "application/pdf")},
            headers=headers,
        )
        accepted = client.post(
            "/api/v1/reports/analyze",
            files={"file": ("../synthetic.pdf", b"%PDF synthetic", "application/pdf")},
            headers=headers,
        )

    assert mismatched.status_code == 400
    assert "文件内容" in mismatched.json()["detail"]
    assert accepted.status_code == 200
    assert accepted.json()["filename"] == "synthetic.pdf"
    assert accepted.json()["storage_provider"] == "local_private"
    assert accepted.json()["file_size"] == len(b"%PDF synthetic")


def test_report_fields_must_be_reviewed_before_ranking():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        analyzed = client.post(
            "/api/v1/reports/analyze",
            files={"file": ("review.pdf", b"%PDF synthetic", "application/pdf")},
            headers=headers,
        )
        assert analyzed.status_code == 200
        payload = analyzed.json()
        assert payload["ocr_status"] == "completed"
        assert payload["ocr_provider"] == "mock_ocr"
        assert all(metric["raw_text"] for metric in payload["metrics"])
        assert all(len(metric["source_bbox"]) == 4 for metric in payload["metrics"])

        premature = client.post(
            f"/api/v1/reports/{payload['report_id']}/confirm", headers=headers
        )
        blocked_actions = client.get("/api/v1/actions", headers=headers)
        assert premature.status_code == 409
        assert "未逐项确认" in premature.json()["detail"]
        assert blocked_actions.status_code == 200
        assert blocked_actions.json() == []

        first, second, *remaining = payload["metrics"]
        confirmed = client.post(
            f"/api/v1/reports/{payload['report_id']}/metrics/{first['id']}/confirm",
            headers=headers,
        )
        corrected = client.patch(
            f"/api/v1/reports/{payload['report_id']}/metrics/{second['id']}",
            json={
                "name": second["name"],
                "value": second["value"] + 0.1,
                "unit": second["unit"],
                "reference_range": second["reference_range"],
            },
            headers=headers,
        )
        assert confirmed.json()["review_status"] == "confirmed"
        assert corrected.json()["review_status"] == "corrected"
        assert corrected.json()["extracted_value"] == second["value"]

        for metric in remaining:
            response = client.post(
                f"/api/v1/reports/{payload['report_id']}/metrics/{metric['id']}/confirm",
                headers=headers,
            )
            assert response.status_code == 200

        finalized = client.post(
            f"/api/v1/reports/{payload['report_id']}/confirm", headers=headers
        )
        ranked_actions = client.get("/api/v1/actions", headers=headers)
        source = client.get(
            f"/api/v1/reports/{payload['report_id']}/source", headers=headers
        )
        reviewer_headers = login_demo(client, "demo-reviewer")
        reviewer_source = client.get(
            f"/api/v1/reports/{payload['report_id']}/source",
            headers=reviewer_headers,
        )

    assert finalized.status_code == 200
    assert len(ranked_actions.json()) == 3
    assert source.status_code == 200
    assert source.content == b"%PDF synthetic"
    assert source.headers["cache-control"] == "private, no-store"
    assert reviewer_source.status_code == 403


def test_ocr_failure_persists_retryable_state_without_metrics():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        failed = client.post(
            "/api/v1/reports/analyze",
            files={
                "file": (
                    "failure.pdf",
                    b"%PDF YUNSYNC_SCENARIO:failure",
                    "application/pdf",
                )
            },
            headers=headers,
        )
        assert failed.status_code == 503
        report_id = failed.json()["detail"]["report_id"]
        latest = client.get("/api/v1/reports/latest", headers=headers)
        actions = client.get("/api/v1/actions", headers=headers)
        retried = client.post(f"/api/v1/reports/{report_id}/retry", headers=headers)

    assert latest.status_code == 200
    assert latest.json()["report_id"] == report_id
    assert latest.json()["ocr_status"] == "failed"
    assert latest.json()["metrics"] == []
    assert actions.json() == []
    assert retried.status_code == 503
    assert retried.json()["detail"]["report_id"] == report_id


def test_ocr_timeout_uses_bounded_retries_without_metrics():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        timed_out = client.post(
            "/api/v1/reports/analyze",
            files={
                "file": (
                    "timeout.pdf",
                    b"%PDF YUNSYNC_SCENARIO:timeout",
                    "application/pdf",
                )
            },
            headers=headers,
        )
        latest = client.get("/api/v1/reports/latest", headers=headers)

    assert timed_out.status_code == 503
    assert timed_out.json()["detail"]["code"] == "timeout"
    assert latest.json()["ocr_attempts"] == 2
    assert latest.json()["metrics"] == []
