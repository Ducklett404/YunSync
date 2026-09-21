"""Known unit conversions require confirmed values and preserve source data."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.health import HealthMetric, HealthReport
from app.services.identity_service import CURRENT_CONSENT_VERSION
from app.services.unit_policy import UNIT_POLICY_VERSION, project_metric_unit


@pytest.mark.parametrize(
    ("code", "name", "value", "unit", "expected"),
    [
        ("fasting_glucose", "空腹血糖", 100, "mg/dL", 5.55),
        ("total_cholesterol", "总胆固醇", 200, "mg/dL", 200 / 38.67),
        ("ldl_c", "低密度脂蛋白胆固醇", 130, "mg/dL", 130 / 38.67),
        ("hdl_c", "高密度脂蛋白胆固醇", 50, "mg/dL", 50 / 38.67),
        ("triglyceride", "甘油三酯", 150, "mg/dL", 150 / 88.57),
    ],
)
def test_confirmed_common_units_project_without_changing_source(
    code, name, value, unit, expected
):
    result = project_metric_unit(
        code=code, name=name, value=value, unit=unit, confirmed=True
    )
    assert result.status == "converted"
    assert result.standard_value == pytest.approx(expected)
    assert result.standard_unit == "mmol/L"
    assert result.rule_version == UNIT_POLICY_VERSION


def test_unconfirmed_unknown_and_unsupported_units_do_not_get_a_value():
    cases = [
        ("fasting_glucose", "空腹血糖", 100, "mg/dL", False, "unconfirmed"),
        ("creatinine", "肌酐", 1.0, "mg/dL", True, "unsupported_unit"),
        ("bun", "BUN", 20, "mg/dL", True, "outside_catalog"),
        ("fasting_glucose", "尿酸", 100, "mg/dL", True, "identity_conflict"),
    ]
    for code, name, value, unit, confirmed, expected_status in cases:
        result = project_metric_unit(
            code=code, name=name, value=value, unit=unit, confirmed=confirmed
        )
        assert result.status == expected_status
        assert result.standard_value is None

    canonical = project_metric_unit(
        code="bmi", name="身体质量指数", value=23.1, unit="kg/m2", confirmed=True
    )
    assert canonical.status == "as_reported"
    assert canonical.standard_value == 23.1
    assert canonical.standard_unit == "kg/m²"


def test_report_api_blocks_unknown_unit_until_user_corrects_confirmed_field():
    report_id, metric_id = str(uuid4()), str(uuid4())
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/demo", json={"account_id": "demo-student"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        client.post(
            "/api/v1/consents/accept",
            json={"version": CURRENT_CONSENT_VERSION},
            headers=headers,
        )
        with SessionLocal() as db:
            db.add(
                HealthReport(
                    id=report_id,
                    user_id="demo-user",
                    filename="单位待核对合成报告.pdf",
                    ocr_status="completed",
                    status="needs_confirmation",
                    created_at=datetime.now(timezone.utc) + timedelta(days=30),
                )
            )
            db.flush()
            db.add(
                HealthMetric(
                    id=metric_id,
                    report_id=report_id,
                    user_id="demo-user",
                    code="fasting_glucose",
                    name="空腹血糖",
                    value=100,
                    unit="OCR-unknown",
                    reference_range="70-110",
                    extracted_value=100,
                    extracted_unit="OCR-unknown",
                    extracted_reference_range="70-110",
                )
            )
            db.commit()

        try:
            before = client.get(f"/api/v1/reports/{report_id}", headers=headers)
            confirmed = client.post(
                f"/api/v1/reports/{report_id}/metrics/{metric_id}/confirm", headers=headers
            )
            blocked = client.post(f"/api/v1/reports/{report_id}/confirm", headers=headers)
            safety = client.get("/api/v1/safety/decision", headers=headers)
            corrected = client.patch(
                f"/api/v1/reports/{report_id}/metrics/{metric_id}",
                json={
                    "name": "空腹血糖",
                    "value": 100,
                    "unit": "mg/dL",
                    "reference_range": "70-110",
                },
                headers=headers,
            )
            finalized = client.post(f"/api/v1/reports/{report_id}/confirm", headers=headers)

            assert before.json()["metrics"][0]["unit_projection"]["status"] == "unconfirmed"
            assert confirmed.json()["unit_projection"]["status"] == "unsupported_unit"
            assert blocked.status_code == 409
            assert "名称或单位待核对" in blocked.json()["detail"]
            assert "报告指标名称或单位核对" in safety.json()["missing_items"]
            assert corrected.status_code == 200
            assert corrected.json()["unit_projection"]["status"] == "converted"
            assert corrected.json()["unit_projection"]["standard_value"] == pytest.approx(5.55)
            assert corrected.json()["extracted_unit"] == "OCR-unknown"
            assert corrected.json()["reference_range"] == "70-110"
            assert finalized.status_code == 200
        finally:
            with SessionLocal() as db:
                report = db.get(HealthReport, report_id)
                if report is not None:
                    db.delete(report)
                    db.commit()


def test_legacy_confirmed_report_can_reopen_only_for_unresolved_unit():
    report_id, metric_id = str(uuid4()), str(uuid4())
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/demo", json={"account_id": "demo-student"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        client.post(
            "/api/v1/consents/accept",
            json={"version": CURRENT_CONSENT_VERSION},
            headers=headers,
        )
        with SessionLocal() as db:
            db.add(
                HealthReport(
                    id=report_id,
                    user_id="demo-user",
                    filename="旧版已确认报告.pdf",
                    ocr_status="completed",
                    status="confirmed",
                    created_at=datetime.now(timezone.utc) + timedelta(days=31),
                )
            )
            db.flush()
            db.add(
                HealthMetric(
                    id=metric_id,
                    report_id=report_id,
                    user_id="demo-user",
                    code="fasting_glucose",
                    name="空腹血糖",
                    value=100,
                    unit="OCR-unknown",
                    extracted_value=100,
                    extracted_unit="OCR-unknown",
                    confirmed=True,
                    review_status="confirmed",
                )
            )
            db.commit()

        try:
            corrected = client.patch(
                f"/api/v1/reports/{report_id}/metrics/{metric_id}",
                json={
                    "name": "空腹血糖",
                    "value": 100,
                    "unit": "mg/dL",
                    "reference_range": "",
                },
                headers=headers,
            )
            reopened = client.get(f"/api/v1/reports/{report_id}", headers=headers)
            finalized = client.post(f"/api/v1/reports/{report_id}/confirm", headers=headers)
            locked = client.patch(
                f"/api/v1/reports/{report_id}/metrics/{metric_id}",
                json={
                    "name": "空腹血糖",
                    "value": 101,
                    "unit": "mg/dL",
                    "reference_range": "",
                },
                headers=headers,
            )

            assert corrected.status_code == 200
            assert corrected.json()["unit_projection"]["status"] == "converted"
            assert corrected.json()["extracted_unit"] == "OCR-unknown"
            assert reopened.json()["status"] == "needs_confirmation"
            assert finalized.status_code == 200
            assert locked.status_code == 409
        finally:
            with SessionLocal() as db:
                report = db.get(HealthReport, report_id)
                if report is not None:
                    db.delete(report)
                    db.commit()
