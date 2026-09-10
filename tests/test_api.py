from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app


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
        response = client.get("/api/v1/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["report"]["source"] == "synthetic"
    assert len(payload["metrics"]) >= 5
    assert len(payload["actions"]) == 3
    assert payload["experiment"]["progress"] >= 5


def test_report_rejects_unsupported_file_type():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/reports/analyze",
            files={"file": ("notes.txt", b"not a report", "text/plain")},
        )

    assert response.status_code == 400


def test_observation_cannot_override_randomized_condition():
    with TestClient(app) as client:
        experiment = client.get("/api/v1/experiments/current").json()
        day = next(item for item in experiment["schedule"] if item["date"] <= date.today().isoformat())
        response = client.post(
            f"/api/v1/experiments/{experiment['id']}/observations",
            json={
                "observed_on": day["date"],
                "treatment": not day["treatment"],
                "completed": True,
                "steps_30m": 1200,
            },
        )

    assert response.status_code == 400
    assert "随机日程不一致" in response.json()["detail"]


def test_future_observation_is_rejected():
    with TestClient(app) as client:
        experiment = client.get("/api/v1/experiments/current").json()
        day = next(item for item in experiment["schedule"] if item["date"] > date.today().isoformat())
        response = client.post(
            f"/api/v1/experiments/{experiment['id']}/observations",
            json={"observed_on": day["date"], "completed": True, "steps_30m": 1200},
        )

    assert response.status_code == 400
    assert "未来日期" in response.json()["detail"]


def test_drink_experiment_uses_drink_count_as_result_metric():
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/experiments",
            json={
                "user_id": "demo-user",
                "action_id": "action-drink-swap",
                "start_date": (date.today() - timedelta(days=13)).isoformat(),
            },
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
            )
            assert response.status_code == 200

        result = client.get(f"/api/v1/experiments/{experiment['id']}/result")

    assert result.status_code == 200
    assert result.json()["metric_code"] == "sugary_drinks"
    assert result.json()["metric_unit"] == "次"
    assert result.json()["treatment_average"] == 0.5
    assert result.json()["control_average"] == 2.5
