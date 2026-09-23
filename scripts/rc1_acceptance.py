from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SAFE_SCREENING = {
    "acute_symptoms": False,
    "clinician_restriction": False,
    "recent_discomfort": False,
    "support_needed": False,
}


def require(response, label: str, status_code: int = 200) -> dict:
    if response.status_code != status_code:
        raise AssertionError(
            f"{label} failed: expected {status_code}, got {response.status_code}: "
            f"{response.text[:300]}"
        )
    if not response.content:
        return {}
    payload = response.json()
    return payload if isinstance(payload, dict) else {"items": payload}


def run_round(client, round_number: int) -> dict:
    started = perf_counter()
    checks: list[str] = []

    require(client.get("/healthz"), "health check")
    require(client.get("/readyz"), "readiness check")
    checks.append("service_ready")

    login = require(
        client.post("/api/v1/auth/demo", json={"account_id": "demo-student"}),
        "demo login",
    )
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    checks.append("demo_login")

    notice = require(
        client.get("/api/v1/consents/notice", headers=headers),
        "consent notice",
    )
    require(
        client.post(
            "/api/v1/consents/accept",
            json={"version": notice["version"]},
            headers=headers,
        ),
        "consent acceptance",
    )
    profile = require(
        client.post(
            "/api/v1/profile/screening",
            json=SAFE_SCREENING,
            headers=headers,
        ),
        "safety screening",
    )
    assert profile["screening_status"] == "eligible" and not profile["high_risk"]
    checks.append("consent_and_screening")

    report = require(
        client.get("/api/v1/reports/latest", headers=headers), "latest report"
    )
    assert report["source"] == "synthetic"
    assert report["metrics"] and all(item["confirmed"] for item in report["metrics"])
    checks.append("confirmed_report")

    actions = require(client.get("/api/v1/actions", headers=headers), "ranked actions")
    assert len(actions["items"]) == 3
    checks.append("ranked_actions")

    experiment = require(
        client.get("/api/v1/experiments/current", headers=headers),
        "current experiment",
    )
    assert len(experiment["schedule"]) == 14
    checks.append("experiment_schedule")

    result = require(
        client.get(
            f"/api/v1/experiments/{experiment['id']}/result", headers=headers
        ),
        "experiment result",
    )
    assert result["analysis_version"]
    assert "不构成诊断或治疗建议" in result["explanation"]
    checks.append("safe_result")

    dashboard = require(
        client.get("/api/v1/dashboard", headers=headers), "dashboard"
    )
    assert dashboard["report"]["source"] == "synthetic"
    assert "合成数据" in dashboard["notice"]
    checks.append("dashboard")

    require(client.post("/api/v1/auth/logout", headers=headers), "logout")
    checks.append("logout")

    return {
        "round": round_number,
        "status": "passed",
        "checks": checks,
        "duration_ms": round((perf_counter() - started) * 1000, 2),
    }


def run_acceptance(rounds: int) -> dict:
    if rounds < 1:
        raise ValueError("rounds must be at least 1")

    with tempfile.TemporaryDirectory(prefix="yunsync-rc1-") as temp_dir:
        temp_root = Path(temp_dir)
        os.environ.update(
            {
                "ENVIRONMENT": "test",
                "DATABASE_URL": f"sqlite:///{(temp_root / 'acceptance.db').as_posix()}",
                "UPLOAD_STORAGE_DIR": str(temp_root / "uploads"),
                "ENABLE_DEMO_LOGIN": "true",
                "SEED_DEMO_DATA": "true",
                "USE_MOCK_AI": "true",
                "USE_LOCAL_STORAGE": "true",
                "CACHE_ENABLED": "false",
                "ALLOWED_HOSTS": "testserver,localhost,127.0.0.1",
            }
        )
        sys.path.insert(0, str(BACKEND))

        from fastapi.testclient import TestClient

        from app.db.session import engine
        from app.main import app

        try:
            with TestClient(app) as client:
                results = [run_round(client, index + 1) for index in range(rounds)]
        finally:
            engine.dispose()

    durations = [item["duration_ms"] for item in results]
    return {
        "mode": "synthetic",
        "rounds": rounds,
        "successful_rounds": len(results),
        "task_success_rate": 1.0,
        "median_round_ms": round(statistics.median(durations), 2),
        "results": results,
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Run the YunSync RC1 synthetic main-flow acceptance check."
    )
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    summary = run_acceptance(args.rounds)
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
