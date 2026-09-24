from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.integrations.huawei.obs import LocalPrivateStorageClient, ObjectStorageError
from app.main import app
from app.models.care_plan import CarePlan
from app.models.experiment import Experiment
from app.models.health import HealthReport
from app.models.privacy import PrivacyRequest
from app.models.user import UserProfile
from app.services.privacy_service import privacy_service


def _login(client: TestClient, account_id: str = "demo-student") -> dict[str, str]:
    response = client.post("/api/v1/auth/demo", json={"account_id": account_id})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _accept(client: TestClient, headers: dict[str, str]) -> None:
    notice = client.get("/api/v1/consents/notice", headers=headers).json()
    response = client.post(
        "/api/v1/consents/accept", headers=headers, json={"version": notice["version"]}
    )
    assert response.status_code == 200


def _activity_snapshot() -> tuple[list[tuple], list[tuple]]:
    with SessionLocal() as db:
        experiments = [
            (item.id, item.status, item.paused_at, item.updated_at)
            for item in db.scalars(select(Experiment).where(Experiment.user_id == "demo-user"))
        ]
        plans = [
            (item.id, item.status, item.paused_at, item.pause_reason)
            for item in db.scalars(select(CarePlan).where(CarePlan.user_id == "demo-user"))
        ]
    return experiments, plans


def _restore_activity(snapshot: tuple[list[tuple], list[tuple]]) -> None:
    experiments, plans = snapshot
    with SessionLocal() as db:
        for item_id, status, paused_at, updated_at in experiments:
            if item := db.get(Experiment, item_id):
                item.status, item.paused_at, item.updated_at = status, paused_at, updated_at
        for item_id, status, paused_at, pause_reason in plans:
            if item := db.get(CarePlan, item_id):
                item.status, item.paused_at, item.pause_reason = status, paused_at, pause_reason
        db.commit()


def test_account_export_is_private_and_available_after_withdrawal():
    with TestClient(app) as client:
        snapshot = _activity_snapshot()
        headers = _login(client)
        _accept(client, headers)
        assert client.post("/api/v1/consents/withdraw", headers=headers).status_code == 200

        response = client.get("/api/v1/account/export", headers=headers)

        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert "attachment" in response.headers["content-disposition"]
        payload = response.json()
        assert payload["format"] == "yunsync-account-export-v1"
        assert payload["profile"]["id"] == "demo-user"
        raw = response.text.lower()
        assert "token_hash" not in raw
        assert "storage_key" not in raw
        assert "secret_key" not in raw
        _accept(client, headers)
    _restore_activity(snapshot)


def test_reviewer_cannot_export_participant_data():
    with TestClient(app) as client:
        headers = _login(client, "demo-reviewer")
        response = client.get("/api/v1/account/export", headers=headers)
        assert response.status_code == 403


def test_deletion_request_is_idempotent_and_can_be_cancelled():
    with TestClient(app) as client:
        snapshot = _activity_snapshot()
        headers = _login(client)
        _accept(client, headers)
        first = client.post(
            "/api/v1/account/deletion-request",
            headers=headers,
            json={"confirmation": "删除我的云循数据"},
        )
        second = client.post(
            "/api/v1/account/deletion-request",
            headers=headers,
            json={"confirmation": "删除我的云循数据"},
        )
        assert first.status_code == second.status_code == 200
        assert first.json()["id"] == second.json()["id"]
        status = client.get("/api/v1/account/privacy-status", headers=headers).json()
        assert status["active_consent"] is False
        assert status["pending_deletion"]["status"] == "pending"
        notice = client.get("/api/v1/consents/notice", headers=headers).json()
        blocked_consent = client.post(
            "/api/v1/consents/accept",
            headers=headers,
            json={"version": notice["version"]},
        )
        assert blocked_consent.status_code == 409

        cancelled = client.delete("/api/v1/account/deletion-request", headers=headers)
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        _accept(client, headers)
    _restore_activity(snapshot)


def test_report_delete_requires_matching_confirmation():
    with TestClient(app) as client:
        snapshot = _activity_snapshot()
        headers = _login(client)
        _accept(client, headers)
        created = client.post(
            "/api/v1/reports/manual",
            headers=headers,
            json={
                "title": "M9 删除测试",
                "institution": "合成机构",
                "measured_at": datetime.now(timezone.utc).isoformat(),
                "metrics": [
                    {
                        "name": "空腹血糖",
                        "value": 5.2,
                        "unit": "mmol/L",
                        "reference_range": "3.9-6.1",
                        "method": "合成方法",
                    }
                ],
            },
        )
        assert created.status_code == 200
        report_id = created.json()["report_id"]
        mismatch = client.request(
            "DELETE",
            f"/api/v1/reports/{report_id}",
            headers=headers,
            json={"confirm_report_id": "wrong"},
        )
        assert mismatch.status_code == 400
        assert client.post("/api/v1/consents/withdraw", headers=headers).status_code == 200
        deleted = client.request(
            "DELETE",
            f"/api/v1/reports/{report_id}",
            headers=headers,
            json={"confirm_report_id": report_id},
        )
        assert deleted.status_code == 200
        with SessionLocal() as db:
            assert db.get(HealthReport, report_id) is None
        _accept(client, headers)
    _restore_activity(snapshot)


def test_due_deletion_removes_user_data_and_keeps_tombstone(tmp_path: Path):
    user_id = "m9-temp-user"
    storage = LocalPrivateStorageClient(tmp_path)
    stored = storage.put_private(b"synthetic", user_id=user_id, suffix=".pdf")
    with SessionLocal() as db:
        user = UserProfile(id=user_id, nickname="临时用户")
        db.add(user)
        db.flush()
        db.add(
            HealthReport(
                user_id=user_id,
                filename="temp.pdf",
                storage_provider="local_private",
                storage_key=stored.key,
            )
        )
        request = PrivacyRequest(
            user_id=user_id,
            subject_hash=privacy_service.subject_hash(user_id),
            request_type="account_deletion",
            status="pending",
            requested_at=datetime.now(timezone.utc) - timedelta(days=1),
            execute_after=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db.add(request)
        db.commit()
        request_id = request.id

        original_root = privacy_service._storage
        privacy_service._storage = lambda _report: storage
        try:
            result = privacy_service.process_due_deletions(db)
        finally:
            privacy_service._storage = original_root

        assert result["completed"] == 1
        assert db.get(UserProfile, user_id) is None
        tombstone = db.get(PrivacyRequest, request_id)
        assert tombstone is not None
        assert tombstone.user_id is None
        assert tombstone.status == "completed"
        assert not (tmp_path / stored.key).exists()


def test_local_storage_delete_rejects_escape_and_is_idempotent(tmp_path: Path):
    storage = LocalPrivateStorageClient(tmp_path / "private")
    stored = storage.put_private(b"synthetic", user_id="safe-user", suffix=".pdf")
    storage.delete_private(stored.key)
    storage.delete_private(stored.key)
    assert not (storage.root / stored.key).exists()
    try:
        storage.delete_private("../outside.pdf")
    except ObjectStorageError as exc:
        assert "路径校验失败" in str(exc)
    else:
        raise AssertionError("path traversal must be rejected")
