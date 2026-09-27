"""Confirmed report history aligns codes but never asserts clinical comparability."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.health import HealthMetric, HealthReport
from app.services.identity_service import CURRENT_CONSENT_VERSION


def test_history_aligns_confirmed_reports_and_marks_comparison_limits():
    old_id, new_id, pending_id, foreign_id = (str(uuid4()) for _ in range(4))
    now = datetime.now(timezone.utc)
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/demo", json={"account_id": "demo-student"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        client.post(
            "/api/v1/consents/accept",
            json={"version": CURRENT_CONSENT_VERSION},
            headers=headers,
        )
        with SessionLocal() as db:
            db.add_all(
                [
                    HealthReport(id=old_id, user_id="demo-user", filename="旧报告.pdf", institution="机构甲", examined_at=now - timedelta(days=60), status="confirmed", created_at=now + timedelta(days=20)),
                    HealthReport(id=new_id, user_id="demo-user", filename="新报告.pdf", institution="机构甲", examined_at=now - timedelta(days=1), status="confirmed", created_at=now + timedelta(days=21)),
                    HealthReport(id=pending_id, user_id="demo-user", filename="待确认报告.pdf", status="needs_confirmation", created_at=now + timedelta(days=22)),
                    HealthReport(id=foreign_id, user_id="demo-reviewer", filename="他人报告.pdf", status="confirmed", created_at=now + timedelta(days=23)),
                ]
            )
            db.flush()
            db.add_all(
                [
                    HealthMetric(report_id=old_id, user_id="demo-user", code="fasting_glucose", name="空腹血糖", value=100, unit="mg/dL", reference_range="70-110", method="己糖激酶法", confirmed=True),
                    HealthMetric(report_id=new_id, user_id="demo-user", code="fpg", name="FPG", value=6.0, unit="mmol/L", reference_range="3.9-6.1", method="己糖激酶法", confirmed=True),
                    HealthMetric(report_id=pending_id, user_id="demo-user", code="fasting_glucose", name="空腹血糖", value=9.0, unit="mmol/L", confirmed=True),
                    HealthMetric(report_id=foreign_id, user_id="demo-reviewer", code="fasting_glucose", name="空腹血糖", value=10.0, unit="mmol/L", confirmed=True),
                    HealthMetric(report_id=old_id, user_id="demo-user", code="triglyceride", name="甘油三酯", value=150, unit="mg/dL", method="酶法", confirmed=True),
                    HealthMetric(report_id=new_id, user_id="demo-user", code="triglyceride", name="甘油三酯", value=2.0, unit="unverified", method="酶法", confirmed=True),
                    HealthMetric(report_id=old_id, user_id="demo-user", code="ldl_c", name="LDL-C", value=120, unit="mg/dL", method="直接法", confirmed=True),
                    HealthMetric(report_id=new_id, user_id="demo-user", code="ldl_c", name="LDL-C", value=3.0, unit="mmol/L", method="直接法", confirmed=True),
                    HealthMetric(report_id=new_id, user_id="demo-user", code="ldl", name="低密度脂蛋白", value=3.1, unit="mmol/L", method="直接法", confirmed=True),
                    HealthMetric(report_id=old_id, user_id="demo-user", code="hba1c", name="HbA1c", value=5.6, unit="%", confirmed=True),
                    HealthMetric(report_id=new_id, user_id="demo-user", code="hba1c", name="HbA1c", value=5.8, unit="%", confirmed=True),
                    HealthMetric(report_id=old_id, user_id="demo-user", code="total_cholesterol", name="总胆固醇", value=4.8, unit="mmol/L", method="CHOD-PAP", confirmed=True),
                    HealthMetric(report_id=new_id, user_id="demo-user", code="total_cholesterol", name="总胆固醇", value=5.0, unit="mmol/L", method="氧化酶法", confirmed=True),
                    HealthMetric(report_id=old_id, user_id="demo-user", code="uric_acid", name="尿酸", value=360, reported_precision=0, unit="μmol/L", reference_range="208-428", method="尿酸酶法", confirmed=True),
                    HealthMetric(report_id=new_id, user_id="demo-user", code="uric_acid", name="尿酸", value=380, reported_precision=0, unit="μmol/L", reference_range="208 – 428", method="尿酸酶法", confirmed=True),
                    HealthMetric(report_id=old_id, user_id="demo-user", code="bmi", name="BMI", value=23, unit="kg/m²", method="计算值", confirmed=True),
                    HealthMetric(report_id=new_id, user_id="demo-user", code="bmi", name="BMI", value=24, unit="kg/m²", method="计算值", confirmed=True),
                    HealthMetric(report_id=new_id, user_id="demo-user", code="bun", name="BUN", value=20, unit="mg/dL", confirmed=True),
                    HealthMetric(report_id=new_id, user_id="demo-user", code="height", name="身高", value=170, unit="cm", confirmed=False),
                ]
            )
            db.commit()

        try:
            response = client.get("/api/v1/metrics/summary", headers=headers)
            assert response.status_code == 200
            result = response.json()
            series = {item["code"]: item for item in result["series"]}
            assert result["rule_version"] == "v2-history-draft-4"
            assert "bun" not in series
            assert "height" not in series
            glucose = series["fasting_glucose"]
            assert [point["report_id"] for point in glucose["points"]][-2:] == [old_id, new_id]
            assert pending_id not in [point["report_id"] for point in glucose["points"]]
            assert foreign_id not in [point["report_id"] for point in glucose["points"]]
            assert glucose["points"][-2]["value"] == 100
            assert glucose["points"][-2]["unit"] == "mg/dL"
            assert glucose["points"][-2]["standard_value"] == pytest.approx(5.55)
            assert glucose["latest_pair"]["arithmetic_change"] is None
            assert glucose["latest_pair"]["direction"] is None
            assert glucose["latest_pair"]["status"] == "reference_range_changed"
            assert glucose["latest_pair"]["reference_range_changed"] is True
            assert glucose["latest_pair"]["source_unit_changed"] is True
            assert glucose["latest_pair"]["institution_changed"] is False
            assert glucose["latest_pair"]["method_changed"] is False
            assert any("参考范围不同" in note for note in glucose["latest_pair"]["limitations"])
            uric_acid = series["uric_acid"]
            assert uric_acid["latest_pair"]["status"] == "numeric_only"
            assert uric_acid["latest_pair"]["arithmetic_change"] == pytest.approx(20)
            assert uric_acid["latest_pair"]["direction"] == "higher"
            assert uric_acid["latest_pair"]["reference_range_changed"] is False
            bmi = series["bmi"]
            assert bmi["latest_pair"]["status"] == "reference_range_missing"
            assert bmi["latest_pair"]["arithmetic_change"] is None
            assert any("未填写参考范围" in note for note in bmi["latest_pair"]["limitations"])
            assert series["triglyceride"]["latest_pair"]["status"] == "not_projected"
            assert series["triglyceride"]["latest_pair"]["arithmetic_change"] is None
            assert series["ldl_c"]["latest_pair"]["status"] == "duplicate_in_report"
            assert series["ldl_c"]["latest_pair"]["arithmetic_change"] is None
            assert series["hba1c"]["latest_pair"]["status"] == "metadata_missing"
            assert series["hba1c"]["latest_pair"]["arithmetic_change"] is None
            assert series["total_cholesterol"]["latest_pair"]["status"] == "method_changed"
            assert series["total_cholesterol"]["latest_pair"]["arithmetic_change"] is None

            limited = client.get("/api/v1/metrics/summary", params={"report_limit": 1}, headers=headers)
            assert limited.status_code == 200
            assert limited.json()["reports_considered"] == 1
            assert all(item["latest_pair"] is None for item in limited.json()["series"])
            assert client.get("/api/v1/metrics/summary", params={"report_limit": 51}, headers=headers).status_code == 422
            assert client.get("/api/v1/metrics/summary").status_code == 401
        finally:
            with SessionLocal() as db:
                for report_id in (old_id, new_id, pending_id, foreign_id):
                    report = db.get(HealthReport, report_id)
                    if report is not None:
                        db.delete(report)
                db.commit()
