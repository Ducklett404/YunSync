from pathlib import Path

import pytest

from scripts.performance_smoke import percentile_nearest_rank
from scripts.repository_security_scan import scan_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_secret_scanner_reports_location_without_echoing_secret():
    secret = "ghp_" + "abcdefghijklmnopqrstuvwxyz012345"
    findings = scan_text("sample.txt", f"token={secret}")

    assert len(findings) == 1
    assert findings[0].rule == "github-token"
    assert findings[0].safe_description() == "sample.txt:1 [github-token]"
    assert secret not in findings[0].safe_description()


def test_secret_scanner_allows_documented_placeholders():
    assert scan_text(".env.example", "SECRET_KEY=replace-this-before-deployment") == []


def test_percentile_uses_nearest_rank_and_rejects_empty_input():
    assert percentile_nearest_rank([5.0, 1.0, 3.0, 2.0, 4.0], 95) == 5.0
    with pytest.raises(ValueError, match="empty"):
        percentile_nearest_rank([], 95)


def test_container_definition_runs_as_non_root_with_runtime_guards():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    linux_start = (PROJECT_ROOT / "start.sh").read_text(encoding="utf-8")
    nginx = (PROJECT_ROOT / "deploy" / "nginx.conf.example").read_text(encoding="utf-8")

    assert "USER 10001:10001" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "--no-server-header" in dockerfile
    assert "UPLOAD_STORAGE_DIR=/app/uploads" in dockerfile
    for marker in ("read_only: true", "no-new-privileges:true", "cap_drop:"):
        assert marker in compose
    for marker in (
        "RUN_MIGRATIONS_ON_STARTUP: ${RUN_MIGRATIONS_ON_STARTUP:-false}",
        "UPLOAD_STORAGE_DIR: ${UPLOAD_STORAGE_DIR:-/app/uploads}",
        "MIGRATION_DATABASE_URL",
        "condition: service_completed_successfully",
    ):
        assert marker in compose
    assert "pip install -r requirements-dev.txt" in linux_start
    assert "npm ci" in linux_start
    for marker in ("ssl_protocols TLSv1.2 TLSv1.3", "limit_req", "X-Forwarded-Proto", "location = /internal/metrics"):
        assert marker in nginx
