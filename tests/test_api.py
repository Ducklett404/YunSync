from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.main import app
from app.models.action import ActionTemplate
from app.models.audit import AuditLog
from app.models.experiment import Experiment, Observation
from app.models.health import HealthMetric
from app.models.identity import AuthSession, ConsentRecord
from app.integrations.huawei.ocr import ExtractedMetric, OcrAnalysis
from app.services.identity_service import CURRENT_CONSENT_VERSION, hash_session_token
from app.integrations.cache import OptionalCache


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


def create_confirmed_report(
    client: TestClient, headers: dict[str, str], filename: str
) -> dict:
    analyzed = client.post(
        "/api/v1/reports/analyze",
        files={"file": (filename, b"%PDF synthetic", "application/pdf")},
        headers=headers,
    )
    assert analyzed.status_code == 200
    payload = analyzed.json()
    for metric in payload["metrics"]:
        confirmed = client.post(
            f"/api/v1/reports/{payload['report_id']}/metrics/{metric['id']}/confirm",
            headers=headers,
        )
        assert confirmed.status_code == 200
    finalized = client.post(
        f"/api/v1/reports/{payload['report_id']}/confirm", headers=headers
    )
    assert finalized.status_code == 200
    return payload


def test_health_and_readiness_endpoints():
    with TestClient(app) as client:
        health = client.get("/healthz")
        ready = client.get("/readyz")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["dependencies"] == {"database": "ready", "cache": "disabled"}
    assert ready.json()["degraded"] is False


def test_readiness_stays_available_when_enabled_cache_is_down(monkeypatch):
    class FailingRedis:
        def ping(self):
            raise RedisError("synthetic outage")

    monkeypatch.setattr(
        "app.main.cache",
        OptionalCache(enabled=True, client=FailingRedis()),
    )
    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["dependencies"]["cache"] == "memory_fallback"
    assert response.json()["degraded"] is True


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
    assert result.json()["treatment_median"] == 0.5
    assert result.json()["control_median"] == 2.5
    assert result.json()["valid_days"] == 4
    assert result.json()["explanation_source"] in {"mock_maas", "policy_fallback"}
    assert "不构成诊断或治疗建议" in result.json()["explanation"]


def test_result_next_step_choice_is_persisted_and_audited():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        experiment = client.get("/api/v1/experiments/current", headers=headers).json()
        selected = client.post(
            f"/api/v1/experiments/{experiment['id']}/next-step",
            json={"code": "extend"},
            headers=headers,
        )
        refreshed = client.get("/api/v1/experiments/current", headers=headers)
        result = client.get(
            f"/api/v1/experiments/{experiment['id']}/result", headers=headers
        )

    with SessionLocal() as db:
        event = db.scalar(
            select(AuditLog)
            .where(
                AuditLog.actor_id == "demo-user",
                AuditLog.event_type == "experiment.next_step_selected",
            )
            .order_by(AuditLog.created_at.desc())
        )

    assert selected.status_code == 200
    assert selected.json()["code"] == "extend"
    assert selected.json()["selected_at"] is not None
    assert refreshed.json()["next_step"] == "extend"
    assert result.json()["recommended_next_step"] in {
        "keep",
        "adjust",
        "extend",
        "stop",
    }
    selected_option = next(
        item for item in result.json()["next_step_options"] if item["code"] == "extend"
    )
    assert selected_option["selected"] is True
    assert event is not None
    assert event.payload == {"experiment_id": experiment["id"], "code": "extend"}


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
    assert accepted.json()["source_available"] is True
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


def test_duplicate_ocr_metric_codes_are_rejected_without_partial_rows(monkeypatch):
    class DuplicateMetricClient:
        provider = "duplicate_test_double"

        async def analyze(self, _content, _filename):
            duplicated = ExtractedMetric(
                code="bmi",
                name="身体质量指数",
                value=25.8,
                unit="kg/m²",
                reference_range="18.5-23.9",
                raw_text="身体质量指数 25.8 kg/m²",
                confidence=0.98,
                source_page=1,
                source_bbox=[0.1, 0.1, 0.3, 0.05],
            )
            return OcrAnalysis(
                provider=self.provider,
                page_count=1,
                metrics=[duplicated, duplicated],
            )

    monkeypatch.setattr(
        "app.services.report_service.get_ocr_client",
        lambda: DuplicateMetricClient(),
    )
    with TestClient(app) as client:
        headers = authorize_demo(client)
        response = client.post(
            "/api/v1/reports/analyze",
            files={"file": ("duplicate.pdf", b"%PDF synthetic", "application/pdf")},
            headers=headers,
        )
        latest = client.get("/api/v1/reports/latest", headers=headers)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "duplicate_metric_codes"
    assert latest.status_code == 200
    assert latest.json()["metrics"] == []


def test_database_rejects_duplicate_metric_code_within_one_report():
    with SessionLocal() as db:
        source = db.scalar(
            select(HealthMetric).where(HealthMetric.report_id == "demo-report").limit(1)
        )
        assert source is not None
        db.add(
            HealthMetric(
                report_id=source.report_id,
                user_id=source.user_id,
                code=source.code,
                name=source.name,
                value=source.value,
                unit=source.unit,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_participant_can_export_only_their_experiment_as_private_json():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        experiment = client.get("/api/v1/experiments/current", headers=headers).json()
        exported = client.get(
            f"/api/v1/experiments/{experiment['id']}/export",
            headers=headers,
        )
        reviewer_headers = login_demo(client, "demo-reviewer")
        forbidden = client.get(
            f"/api/v1/experiments/{experiment['id']}/export",
            headers=reviewer_headers,
        )

    assert exported.status_code == 200
    assert exported.headers["cache-control"] == "private, no-store"
    assert exported.headers["content-type"].startswith("application/json")
    assert "attachment" in exported.headers["content-disposition"]
    payload = exported.json()
    assert payload["schema_version"] == "yunsync-experiment-export-v1"
    assert payload["experiment"]["id"] == experiment["id"]
    assert payload["result"]["experiment_id"] == experiment["id"]
    assert "不构成诊断" in payload["notice"]
    assert forbidden.status_code == 403


def test_ranked_actions_expose_template_governance_and_score_breakdown():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        create_confirmed_report(client, headers, "ranking.pdf")
        response = client.get("/api/v1/actions", headers=headers)

    assert response.status_code == 200
    actions = response.json()
    assert len(actions) == 3
    assert [action["score"] for action in actions] == sorted(
        [action["score"] for action in actions], reverse=True
    )
    for action in actions:
        assert action["template_version"] == "1.0.0"
        assert action["review_status"] == "prototype_approved"
        assert action["review_label"] == "产品规则校验（待专业复核）"
        assert action["ranking_policy_version"] == "rank-v1"
        assert action["explanation_policy_version"] == "action-explain-v1"
        assert action["explanation_source"] == "mock_maas"
        assert "不构成诊断或治疗建议" in action["explanation"]
        assert action["score_components"]["total"] == action["score"]
        assert sum(
            action["score_components"][key]
            for key in ("evidence_points", "observability_points", "ease_points")
        ) == pytest.approx(action["score"])
        assert len(action["safety_checks"]) == 4


def test_unsafe_model_explanation_is_replaced_by_policy_fallback(monkeypatch):
    class UnsafeClient:
        provider = "unsafe_test_double"

        async def explain_action(self, context):
            return f"“{context.title}”证明你患有疾病，应自行调整药物并修改剂量。"

    monkeypatch.setattr(
        "app.services.action_service.get_maas_client", lambda: UnsafeClient()
    )
    with TestClient(app) as client:
        headers = authorize_demo(client)
        create_confirmed_report(client, headers, "unsafe-explanation.pdf")
        response = client.get("/api/v1/actions", headers=headers)

    assert response.status_code == 200
    assert response.json()
    for action in response.json():
        assert action["explanation_source"] == "policy_fallback"
        assert "患有疾病" not in action["explanation"]
        assert "调整药物" not in action["explanation"]


def test_reviewer_can_version_activate_and_retire_prototype_templates():
    with TestClient(app) as client:
        participant_headers = authorize_demo(client)
        create_confirmed_report(client, participant_headers, "template-admin.pdf")
        forbidden = client.get(
            "/api/v1/admin/action-templates", headers=participant_headers
        )

        reviewer_headers = login_demo(client, "demo-reviewer")
        listing = client.get(
            "/api/v1/admin/action-templates", headers=reviewer_headers
        )
        source = next(
            item for item in listing.json() if item["code"] == "postmeal_walk"
        )
        created = client.post(
            f"/api/v1/admin/action-templates/{source['id']}/versions",
            json={"version": "2.0.0-test"},
            headers=reviewer_headers,
        )
        duplicate = client.post(
            f"/api/v1/admin/action-templates/{source['id']}/versions",
            json={"version": "2.0.0-test"},
            headers=reviewer_headers,
        )
        draft_active = client.patch(
            f"/api/v1/admin/action-templates/{created.json()['id']}/status",
            json={"review_status": "draft", "is_active": True},
            headers=reviewer_headers,
        )
        activated = client.patch(
            f"/api/v1/admin/action-templates/{created.json()['id']}/status",
            json={"review_status": "prototype_approved", "is_active": True},
            headers=reviewer_headers,
        )
        candidates = client.get("/api/v1/actions", headers=participant_headers)
        inactive_experiment = client.post(
            "/api/v1/experiments",
            json={"action_id": source["id"]},
            headers=participant_headers,
        )
        with SessionLocal() as db:
            active_template = db.get(ActionTemplate, created.json()["id"])
            assert active_template is not None
            active_template.signal_metric_codes = ["metric-not-in-report"]
            db.commit()
        unsupported_signal_experiment = client.post(
            "/api/v1/experiments",
            json={"action_id": created.json()["id"]},
            headers=participant_headers,
        )
        with SessionLocal() as db:
            active_template = db.get(ActionTemplate, created.json()["id"])
            assert active_template is not None
            active_template.signal_metric_codes = source["signal_metric_codes"]
            db.commit()
        active_experiment = client.post(
            "/api/v1/experiments",
            json={"action_id": created.json()["id"]},
            headers=participant_headers,
        )
        retired = client.patch(
            f"/api/v1/admin/action-templates/{created.json()['id']}/status",
            json={"review_status": "retired", "is_active": False},
            headers=reviewer_headers,
        )
        restored = client.patch(
            f"/api/v1/admin/action-templates/{source['id']}/status",
            json={"review_status": "prototype_approved", "is_active": True},
            headers=reviewer_headers,
        )

    assert forbidden.status_code == 403
    assert listing.status_code == 200
    assert created.status_code == 200
    assert created.json()["review_status"] == "draft"
    assert created.json()["is_active"] is False
    assert duplicate.status_code == 409
    assert draft_active.status_code == 409
    assert activated.status_code == 200
    assert any(
        item["id"] == created.json()["id"]
        and item["template_version"] == "2.0.0-test"
        for item in candidates.json()
    )
    assert inactive_experiment.status_code == 409
    assert unsupported_signal_experiment.status_code == 409
    assert "已确认指标不支持" in unsupported_signal_experiment.json()["detail"]
    assert active_experiment.status_code == 200
    assert retired.json()["review_status"] == "retired"
    assert retired.json()["is_active"] is False
    assert restored.json()["is_active"] is True


def test_experiment_state_machine_pauses_resumes_and_blocks_terminal_updates():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        create_confirmed_report(client, headers, "state-machine.pdf")
        action = client.get("/api/v1/actions", headers=headers).json()[0]
        created = client.post(
            "/api/v1/experiments",
            json={"action_id": action["id"], "start_date": date.today().isoformat()},
            headers=headers,
        )
        experiment = created.json()
        day = experiment["schedule"][0]
        paused = client.post(
            f"/api/v1/experiments/{experiment['id']}/pause", headers=headers
        )
        blocked_while_paused = client.post(
            f"/api/v1/experiments/{experiment['id']}/observations",
            json={"observed_on": day["date"], "completed": True},
            headers=headers,
        )
        resumed = client.post(
            f"/api/v1/experiments/{experiment['id']}/resume", headers=headers
        )
        terminated = client.post(
            f"/api/v1/experiments/{experiment['id']}/terminate", headers=headers
        )
        terminal_resume = client.post(
            f"/api/v1/experiments/{experiment['id']}/resume", headers=headers
        )
        terminal_save = client.post(
            f"/api/v1/experiments/{experiment['id']}/observations",
            json={"observed_on": day["date"], "completed": True},
            headers=headers,
        )

    assert created.status_code == 200
    assert experiment["status"] == "active"
    assert experiment["schedule_version"] == "balanced-14-v1"
    assert len(experiment["randomization_seed"].__str__()) == 6
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert paused.json()["paused_at"] is not None
    assert blocked_while_paused.status_code == 400
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "active"
    assert resumed.json()["paused_at"] is None
    assert terminated.status_code == 200
    assert terminated.json()["status"] == "terminated"
    assert terminated.json()["terminated_at"] is not None
    assert terminated.json()["allowed_transitions"] == []
    assert terminal_resume.status_code == 409
    assert terminal_save.status_code == 400


def test_new_experiment_pauses_previous_and_duplicate_day_updates_in_place():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        create_confirmed_report(client, headers, "single-active.pdf")
        actions = client.get("/api/v1/actions", headers=headers).json()
        first = client.post(
            "/api/v1/experiments",
            json={"action_id": actions[0]["id"], "start_date": date.today().isoformat()},
            headers=headers,
        ).json()
        second_response = client.post(
            "/api/v1/experiments",
            json={"action_id": actions[1]["id"], "start_date": date.today().isoformat()},
            headers=headers,
        )
        second = second_response.json()
        conflicting_resume = client.post(
            f"/api/v1/experiments/{first['id']}/resume", headers=headers
        )
        day = second["schedule"][0]
        first_save = client.post(
            f"/api/v1/experiments/{second['id']}/observations",
            json={
                "observed_on": day["date"],
                "completed": False,
                "sugary_drinks": 2,
            },
            headers=headers,
        )
        second_save = client.post(
            f"/api/v1/experiments/{second['id']}/observations",
            json={
                "observed_on": day["date"],
                "completed": True,
                "sugary_drinks": 1,
            },
            headers=headers,
        )
        refreshed = client.get("/api/v1/experiments/current", headers=headers)

        with SessionLocal() as db:
            stored_first = db.get(Experiment, first["id"])
            active_count = db.scalar(
                select(func.count())
                .select_from(Experiment)
                .where(Experiment.user_id == "demo-user", Experiment.status == "active")
            )
            saved = list(
                db.scalars(
                    select(Observation).where(Observation.experiment_id == second["id"])
                )
            )

        terminated_second = client.post(
            f"/api/v1/experiments/{second['id']}/terminate", headers=headers
        )
        resumed_first = client.post(
            f"/api/v1/experiments/{first['id']}/resume", headers=headers
        )
        client.post(f"/api/v1/experiments/{first['id']}/terminate", headers=headers)

    assert second_response.status_code == 200
    assert stored_first is not None and stored_first.status == "paused"
    assert stored_first.paused_at is not None
    assert active_count == 1
    assert conflicting_resume.status_code == 409
    assert first_save.status_code == 200
    assert second_save.status_code == 200
    assert len(saved) == 1
    assert saved[0].completed is True
    assert saved[0].sugary_drinks == 1
    assert refreshed.json()["recorded_days"] == 1
    assert refreshed.json()["completed_days"] == 1
    assert refreshed.json()["schedule"][0]["recorded"] is True
    assert terminated_second.status_code == 200
    assert resumed_first.status_code == 200


def test_experiment_completion_requires_period_end_and_all_fourteen_records():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        create_confirmed_report(client, headers, "complete-experiment.pdf")
        action = client.get("/api/v1/actions", headers=headers).json()[0]
        created = client.post(
            "/api/v1/experiments",
            json={
                "action_id": action["id"],
                "start_date": (date.today() - timedelta(days=13)).isoformat(),
            },
            headers=headers,
        ).json()
        premature = client.post(
            f"/api/v1/experiments/{created['id']}/complete", headers=headers
        )
        for index, day in enumerate(created["schedule"]):
            saved = client.post(
                f"/api/v1/experiments/{created['id']}/observations",
                json={
                    "observed_on": day["date"],
                    "completed": index % 2 == 0,
                    "steps_30m": 900 + index,
                },
                headers=headers,
            )
            assert saved.status_code == 200
        ready = client.get("/api/v1/experiments/current", headers=headers)
        completed = client.post(
            f"/api/v1/experiments/{created['id']}/complete", headers=headers
        )
        completed_again = client.post(
            f"/api/v1/experiments/{created['id']}/complete", headers=headers
        )
        with SessionLocal() as db:
            lifecycle_events = list(
                db.scalars(
                    select(AuditLog.event_type).where(
                        AuditLog.actor_id == "demo-user",
                        AuditLog.event_type.in_(
                            {
                                "experiment.started",
                                "experiment.paused",
                                "experiment.resumed",
                                "experiment.terminated",
                                "experiment.completed",
                            }
                        ),
                    )
                )
            )

    assert premature.status_code == 409
    assert "14 天记录" in premature.json()["detail"]
    assert ready.status_code == 200
    assert ready.json()["recorded_days"] == 14
    assert "complete" in ready.json()["allowed_transitions"]
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"] is not None
    assert completed.json()["allowed_transitions"] == []
    assert completed_again.status_code == 409
    assert "experiment.completed" in lifecycle_events


def test_out_of_period_and_tampered_schedule_are_rejected():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        create_confirmed_report(client, headers, "locked-schedule.pdf")
        action = client.get("/api/v1/actions", headers=headers).json()[0]
        created = client.post(
            "/api/v1/experiments",
            json={
                "action_id": action["id"],
                "start_date": (date.today() - timedelta(days=2)).isoformat(),
            },
            headers=headers,
        ).json()
        out_of_period = client.post(
            f"/api/v1/experiments/{created['id']}/observations",
            json={
                "observed_on": (date.today() - timedelta(days=3)).isoformat(),
                "completed": True,
            },
            headers=headers,
        )

        with SessionLocal() as db:
            stored = db.get(Experiment, created["id"])
            assert stored is not None
            original_schedule = [dict(day) for day in stored.schedule]
            tampered_schedule = [dict(day) for day in stored.schedule]
            tampered_schedule[0]["label"] = "被篡改"
            stored.schedule = tampered_schedule
            db.commit()
        tampered_current = client.get("/api/v1/experiments/current", headers=headers)
        with SessionLocal() as db:
            stored = db.get(Experiment, created["id"])
            assert stored is not None
            stored.schedule = original_schedule
            db.commit()
        restored_current = client.get("/api/v1/experiments/current", headers=headers)
        client.post(
            f"/api/v1/experiments/{created['id']}/terminate", headers=headers
        )

    assert out_of_period.status_code == 400
    assert "不在实验周期" in out_of_period.json()["detail"]
    assert tampered_current.status_code == 409
    assert "完整性校验失败" in tampered_current.json()["detail"]
    assert restored_current.status_code == 200


def test_three_action_types_accept_only_their_primary_metric():
    cases = {
        "postmeal_walk": ({"steps_30m": 900}, {"sugary_drinks": 1}, "steps_30m"),
        "drink_swap": ({"sugary_drinks": 0}, {"steps_30m": 900}, "sugary_drinks"),
        "meal_order": ({"subjective_score": 4}, {"steps_30m": 900}, "subjective_score"),
    }
    with TestClient(app) as client:
        headers = authorize_demo(client)
        create_confirmed_report(client, headers, "three-action-records.pdf")
        actions = {
            item["code"]: item for item in client.get("/api/v1/actions", headers=headers).json()
        }
        for code, (valid_metric, invalid_metric, metric_name) in cases.items():
            experiment = client.post(
                "/api/v1/experiments",
                json={"action_id": actions[code]["id"], "start_date": date.today().isoformat()},
                headers=headers,
            ).json()
            observed_on = experiment["schedule"][0]["date"]
            rejected = client.post(
                f"/api/v1/experiments/{experiment['id']}/observations",
                json={"observed_on": observed_on, "completed": True, **invalid_metric},
                headers=headers,
            )
            saved = client.post(
                f"/api/v1/experiments/{experiment['id']}/observations",
                json={"observed_on": observed_on, "completed": True, **valid_metric},
                headers=headers,
            )
            refreshed = client.get("/api/v1/experiments/current", headers=headers).json()
            observation = refreshed["schedule"][0]["observation"]

            assert rejected.status_code == 400
            assert "主要指标" in rejected.json()["detail"]
            assert saved.status_code == 200
            assert observation[metric_name] == next(iter(valid_metric.values()))
        client.post(
            f"/api/v1/experiments/{experiment['id']}/terminate", headers=headers
        )


def test_missing_context_and_significant_discomfort_pause_experiment():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        create_confirmed_report(client, headers, "missing-context.pdf")
        action = next(
            item
            for item in client.get("/api/v1/actions", headers=headers).json()
            if item["code"] == "postmeal_walk"
        )
        experiment = client.post(
            "/api/v1/experiments",
            json={"action_id": action["id"], "start_date": date.today().isoformat()},
            headers=headers,
        ).json()
        observed_on = experiment["schedule"][0]["date"]
        without_reason = client.post(
            f"/api/v1/experiments/{experiment['id']}/observations",
            json={"observed_on": observed_on, "completed": False},
            headers=headers,
        )
        saved = client.post(
            f"/api/v1/experiments/{experiment['id']}/observations",
            json={
                "observed_on": observed_on,
                "completed": False,
                "missing_reason": "physical_discomfort",
                "discomfort_level": "significant",
                "discomfort_details": "合成记录：出现明显不适",
                "unplanned_event": "合成记录：临时出行",
            },
            headers=headers,
        )
        refreshed = client.get("/api/v1/experiments/current", headers=headers).json()
        observation = refreshed["schedule"][0]["observation"]

        with SessionLocal() as db:
            pause_event = db.scalar(
                select(AuditLog)
                .where(
                    AuditLog.actor_id == "demo-user",
                    AuditLog.event_type == "experiment.paused",
                )
                .order_by(AuditLog.created_at.desc())
            )

    assert without_reason.status_code == 400
    assert "缺失原因" in without_reason.json()["detail"]
    assert saved.status_code == 200
    assert "自动暂停" in saved.json()["message"]
    assert refreshed["status"] == "paused"
    assert observation["missing_reason"] == "physical_discomfort"
    assert observation["discomfort_level"] == "significant"
    assert observation["unplanned_event"] == "合成记录：临时出行"
    assert pause_event is not None
    assert pause_event.payload["reason"] == "significant_discomfort_reported"


def test_reminder_settings_are_validated_and_persisted():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        invalid = client.patch(
            "/api/v1/profile",
            json={"reminder_enabled": True, "reminder_time": "25:80"},
            headers=headers,
        )
        saved = client.patch(
            "/api/v1/profile",
            json={"reminder_enabled": True, "reminder_time": "19:35"},
            headers=headers,
        )
        fetched = client.get("/api/v1/profile", headers=headers)

    assert invalid.status_code == 422
    assert saved.status_code == 200
    assert saved.json()["reminder_time"] == "19:35"
    assert fetched.json()["reminder_enabled"] is True
    assert fetched.json()["reminder_time"] == "19:35"


def test_csv_and_json_import_templates_are_action_specific_and_idempotent():
    with TestClient(app) as client:
        headers = authorize_demo(client)
        create_confirmed_report(client, headers, "record-import.pdf")
        action = next(
            item
            for item in client.get("/api/v1/actions", headers=headers).json()
            if item["code"] == "drink_swap"
        )
        experiment = client.post(
            "/api/v1/experiments",
            json={
                "action_id": action["id"],
                "start_date": (date.today() - timedelta(days=2)).isoformat(),
            },
            headers=headers,
        ).json()
        eligible_days = experiment["schedule"][:3]
        csv_template = client.get(
            f"/api/v1/experiments/{experiment['id']}/observations/template?format=csv",
            headers=headers,
        )
        json_template = client.get(
            f"/api/v1/experiments/{experiment['id']}/observations/template?format=json",
            headers=headers,
        )
        csv_content = (
            "observed_on,completed,sugary_drinks,sleep_hours,discomfort_level,unplanned_event\n"
            f"{eligible_days[0]['date']},true,0,7.2,none,\n"
            f"{eligible_days[1]['date']},false,2,6.5,none,合成聚餐\n"
        )
        first_import = client.post(
            f"/api/v1/experiments/{experiment['id']}/observations/import",
            json={"format": "csv", "content": csv_content},
            headers=headers,
        )
        repeated_import = client.post(
            f"/api/v1/experiments/{experiment['id']}/observations/import",
            json={"format": "csv", "content": csv_content},
            headers=headers,
        )
        json_import = client.post(
            f"/api/v1/experiments/{experiment['id']}/observations/import",
            json={
                "format": "json",
                "content": (
                    '{"records":[{"observed_on":"'
                    + eligible_days[2]["date"]
                    + '","completed":true,"sugary_drinks":1,"discomfort_level":"none"}]}'
                ),
            },
            headers=headers,
        )
        with SessionLocal() as db:
            rows = list(
                db.scalars(
                    select(Observation).where(Observation.experiment_id == experiment["id"])
                )
            )
        client.post(
            f"/api/v1/experiments/{experiment['id']}/terminate", headers=headers
        )

    assert csv_template.status_code == 200
    assert "sugary_drinks" in csv_template.text
    assert "steps_30m" not in csv_template.text
    assert json_template.status_code == 200
    assert json_template.json()["records"][0]["sugary_drinks"] == 0
    assert first_import.status_code == 200
    assert first_import.json()["created_days"] == 2
    assert repeated_import.status_code == 200
    assert repeated_import.json()["created_days"] == 0
    assert repeated_import.json()["updated_days"] == 2
    assert json_import.status_code == 200
    assert len(rows) == 3
