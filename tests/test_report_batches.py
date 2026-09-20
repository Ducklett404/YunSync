"""Report batch browsing stays scoped to the signed-in participant."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.health import HealthReport
from app.services.identity_service import CURRENT_CONSENT_VERSION


def test_report_batches_are_ordered_paginated_and_owner_scoped():
    newer_id, older_id, other_id = (str(uuid4()) for _ in range(3))
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/demo", json={"account_id": "demo-student"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        client.post(
            "/api/v1/consents/accept",
            json={"version": CURRENT_CONSENT_VERSION},
            headers=headers,
        )
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            db.add_all(
                [
                    HealthReport(
                        id=newer_id,
                        user_id="demo-user",
                        filename="新批次合成报告.pdf",
                        status="needs_confirmation",
                        created_at=now + timedelta(days=3),
                    ),
                    HealthReport(
                        id=older_id,
                        user_id="demo-user",
                        filename="旧批次合成报告.pdf",
                        status="confirmed",
                        created_at=now + timedelta(days=2),
                    ),
                    HealthReport(
                        id=other_id,
                        user_id="demo-reviewer",
                        filename="他人合成报告.pdf",
                        created_at=now + timedelta(days=4),
                    ),
                ]
            )
            db.commit()

        try:
            first = client.get("/api/v1/reports", params={"limit": 1}, headers=headers)
            second = client.get(
                "/api/v1/reports", params={"limit": 1, "offset": 1}, headers=headers
            )
            latest = client.get("/api/v1/reports/latest", headers=headers)
            detail = client.get(f"/api/v1/reports/{older_id}", headers=headers)
            foreign = client.get(f"/api/v1/reports/{other_id}", headers=headers)
            invalid = client.get("/api/v1/reports", params={"limit": 101}, headers=headers)
            anonymous = client.get("/api/v1/reports")

            assert first.status_code == 200
            assert first.json()["items"][0]["report_id"] == newer_id
            assert first.json()["total"] >= 2
            assert second.json()["items"][0]["report_id"] == older_id
            assert latest.json()["report_id"] == newer_id
            assert detail.status_code == 200
            assert detail.json()["filename"] == "旧批次合成报告.pdf"
            assert "storage_key" not in detail.json()
            assert foreign.status_code == 404
            assert invalid.status_code == 422
            assert anonymous.status_code == 401
        finally:
            with SessionLocal() as db:
                for report_id in (newer_id, older_id, other_id):
                    report = db.get(HealthReport, report_id)
                    if report is not None:
                        db.delete(report)
                db.commit()
