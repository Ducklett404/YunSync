"""Manual report batches reuse standardization and explicit confirmation."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.audit import AuditLog
from app.models.health import HealthReport
from app.services.identity_service import CURRENT_CONSENT_VERSION


def _authorize(client: TestClient) -> dict[str, str]:
    login = client.post("/api/v1/auth/demo", json={"account_id": "demo-student"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    client.post(
        "/api/v1/consents/accept",
        json={"version": CURRENT_CONSENT_VERSION},
        headers=headers,
    )
    return headers


def test_manual_report_enters_existing_review_and_confirmation_flow():
    measured_at = datetime.now(timezone.utc) - timedelta(days=2)
    with TestClient(app) as client:
        headers = _authorize(client)
        created = client.post(
            "/api/v1/reports/manual",
            json={
                "title": " 手工录入复查批次 ",
                "institution": " 合成体检机构甲 ",
                "measured_at": measured_at.isoformat(),
                "metrics": [
                    {
                        "name": "FPG",
                        "value": 100,
                        "unit": "mg/dL",
                        "reference_range": "70-110",
                    },
                    {
                        "code": "tg",
                        "name": "TG",
                        "value": 1.6,
                        "unit": "mmol/l",
                        "reference_range": "0.45-1.69",
                        "method": "酶法",
                    },
                    {
                        "name": "白细胞计数",
                        "value": 6.2,
                        "unit": "10^9/L",
                        "reference_range": "3.5-9.5",
                    },
                ],
            },
            headers=headers,
        )
        assert created.status_code == 200
        payload = created.json()
        report_id = payload["report_id"]

        try:
            assert payload["filename"] == "手工录入复查批次"
            assert payload["source"] == "manual"
            assert payload["institution"] == "合成体检机构甲"
            assert payload["examined_at"].startswith(measured_at.date().isoformat())
            assert payload["status"] == "needs_confirmation"
            assert payload["ocr_status"] == "completed"
            assert payload["ocr_provider"] == "manual_entry"
            assert payload["storage_provider"] == "manual_entry"
            assert payload["source_available"] is False
            assert payload["file_size"] == 0
            assert "手工录入" in payload["synthetic_notice"]

            metrics = {metric["name"]: metric for metric in payload["metrics"]}
            glucose = metrics["空腹血糖"]
            assert glucose["code"] == "fasting_glucose"
            assert glucose["unit"] == "mg/dL"
            assert glucose["extracted_unit"] == "mg/dL"
            assert glucose["unit_projection"]["status"] == "unconfirmed"
            assert glucose["confirmed"] is False
            assert glucose["measured_at"].startswith(measured_at.date().isoformat())
            assert metrics["甘油三酯"]["code"] == "triglyceride"
            assert metrics["甘油三酯"]["unit"] == "mmol/L"
            assert metrics["甘油三酯"]["method"] == "酶法"
            assert metrics["白细胞计数"]["code"].startswith("manual_")
            assert metrics["白细胞计数"]["unit_projection"]["status"] == "outside_catalog"
            assert all("手工录入" in metric["raw_text"] for metric in payload["metrics"])

            no_source = client.get(f"/api/v1/reports/{report_id}/source", headers=headers)
            assert no_source.status_code == 409

            confirmed_metrics = []
            for metric in payload["metrics"]:
                confirmed = client.post(
                    f"/api/v1/reports/{report_id}/metrics/{metric['id']}/confirm",
                    headers=headers,
                )
                assert confirmed.status_code == 200
                confirmed_metrics.append(confirmed.json())
            confirmed_glucose = next(
                metric for metric in confirmed_metrics if metric["code"] == "fasting_glucose"
            )
            assert confirmed_glucose["unit_projection"]["status"] == "converted"
            finalized = client.post(f"/api/v1/reports/{report_id}/confirm", headers=headers)
            assert finalized.status_code == 200

            method_updated = client.patch(
                f"/api/v1/reports/{report_id}/metrics/{glucose['id']}",
                json={
                    "name": glucose["name"],
                    "value": glucose["value"],
                    "unit": glucose["unit"],
                    "reference_range": glucose["reference_range"],
                    "method": "己糖激酶法",
                },
                headers=headers,
            )
            assert method_updated.status_code == 200
            assert method_updated.json()["method"] == "己糖激酶法"
            reopened = client.get(f"/api/v1/reports/{report_id}", headers=headers)
            assert reopened.json()["status"] == "needs_confirmation"
            assert client.post(f"/api/v1/reports/{report_id}/confirm", headers=headers).status_code == 200

            revised_examined_at = measured_at - timedelta(days=1)
            metadata_updated = client.patch(
                f"/api/v1/reports/{report_id}/metadata",
                json={
                    "institution": "合成体检机构乙",
                    "examined_at": revised_examined_at.isoformat(),
                },
                headers=headers,
            )
            assert metadata_updated.status_code == 200
            assert metadata_updated.json()["status"] == "needs_confirmation"
            assert metadata_updated.json()["institution"] == "合成体检机构乙"
            assert all(
                metric["measured_at"].startswith(revised_examined_at.date().isoformat())
                for metric in metadata_updated.json()["metrics"]
            )
            assert client.post(f"/api/v1/reports/{report_id}/confirm", headers=headers).status_code == 200
            locked_value_change = client.patch(
                f"/api/v1/reports/{report_id}/metrics/{glucose['id']}",
                json={
                    "name": glucose["name"],
                    "value": glucose["value"] + 1,
                    "unit": glucose["unit"],
                    "reference_range": glucose["reference_range"],
                    "method": "己糖激酶法",
                },
                headers=headers,
            )
            assert locked_value_change.status_code == 409

            with SessionLocal() as db:
                events = list(
                    db.scalars(
                        select(AuditLog)
                        .where(AuditLog.event_type == "report.manual_created")
                        .order_by(AuditLog.created_at.desc())
                    )
                )
                event = next(item for item in events if item.payload["report_id"] == report_id)
                assert event.payload == {
                    "report_id": report_id,
                    "metric_count": 3,
                    "metric_catalog_version": "v2-p0-draft-1",
                }
                metadata_event = next(
                    item
                    for item in db.scalars(
                        select(AuditLog)
                        .where(AuditLog.event_type == "report.metadata_corrected")
                        .order_by(AuditLog.created_at.desc())
                    )
                    if item.payload["report_id"] == report_id
                )
                assert metadata_event.payload == {
                    "report_id": report_id,
                    "changed_fields": ["institution", "examined_at"],
                }
        finally:
            with SessionLocal() as db:
                report = db.get(HealthReport, report_id)
                if report is not None:
                    db.delete(report)
                    db.commit()


def test_manual_report_rejects_duplicates_invalid_time_and_missing_access():
    metric = {
        "name": "空腹血糖",
        "value": 5.6,
        "unit": "mmol/L",
        "reference_range": "3.9-6.1",
    }
    with TestClient(app) as client:
        anonymous = client.post(
            "/api/v1/reports/manual",
            json={
                "title": "未登录批次",
                "measured_at": datetime.now(timezone.utc).isoformat(),
                "metrics": [metric],
            },
        )
        headers = _authorize(client)
        duplicate = client.post(
            "/api/v1/reports/manual",
            json={
                "title": "重复指标批次",
                "measured_at": datetime.now(timezone.utc).isoformat(),
                "metrics": [metric, {**metric, "name": "FPG"}],
            },
            headers=headers,
        )
        future = client.post(
            "/api/v1/reports/manual",
            json={
                "title": "未来批次",
                "measured_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                "metrics": [metric],
            },
            headers=headers,
        )
        too_many = client.post(
            "/api/v1/reports/manual",
            json={
                "title": "超量批次",
                "measured_at": datetime.now(timezone.utc).isoformat(),
                "metrics": [
                    {**metric, "name": f"未知指标 {index}", "code": f"unknown_{index}"}
                    for index in range(31)
                ],
            },
            headers=headers,
        )

    assert anonymous.status_code == 401
    assert duplicate.status_code == 400
    assert "重复录入" in duplicate.json()["detail"]
    assert future.status_code == 422
    assert too_many.status_code == 422
