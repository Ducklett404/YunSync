import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core import monitoring
from app.core.config import Settings, settings
from app.core.demo_case import validate_demo_case
from app.core.observability import request_context_middleware
from app.core.release_readiness import build_release_readiness
from app.main import metrics
from scripts import build_release_package


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _production_settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "environment": "production",
        "secret_key": "a-production-secret-key-value",
        "database_url": "postgresql+psycopg://user:pass@rds.internal/yunsync",
        "cors_origins": "https://app.example.com",
        "allowed_hosts": "app.example.com",
        "forwarded_allow_ips": "10.0.0.8",
        "force_https": True,
        "expose_api_docs": False,
        "rate_limit_enabled": True,
        "monitoring_enabled": True,
        "monitoring_token": "synthetic-monitoring-token-12345",
        "enable_demo_login": False,
        "seed_demo_data": False,
        "run_migrations_on_startup": False,
        "cache_enabled": True,
        "redis_url": "rediss://dcs.internal:6379/0",
        "use_local_storage": False,
        "use_mock_ai": False,
        "huawei_project_id": "synthetic-project-id",
        "huawei_credential_mode": "instance_metadata",
        "huawei_obs_endpoint": "https://obs.example.com",
        "huawei_obs_bucket": "synthetic-private-bucket",
        "huawei_ocr_endpoint": "https://ocr.example.com",
        "huawei_maas_endpoint": "https://maas.example.com",
        "huawei_maas_api_key": "synthetic-api-key",
        "huawei_maas_model": "synthetic-model",
    }
    values.update(overrides)
    return Settings(**values)


def test_metrics_use_route_templates_and_require_token(monkeypatch):
    monitoring.monitoring_registry.reset()
    monkeypatch.setattr(settings, "monitoring_enabled", True)
    monkeypatch.setattr(settings, "monitoring_token", "synthetic-monitoring-token-12345")
    test_app = FastAPI()
    test_app.middleware("http")(request_context_middleware)

    @test_app.get("/objects/{object_id}")
    def read_object(object_id: str):
        return {"available": bool(object_id)}

    client = TestClient(test_app)
    assert client.get("/objects/private-user-123").status_code == 200
    rendered = monitoring.monitoring_registry.render_prometheus()
    assert 'route="/objects/{object_id}"' in rendered
    assert "private-user-123" not in rendered

    with pytest.raises(HTTPException) as denied:
        metrics(None)
    assert denied.value.status_code == 403
    response = metrics("synthetic-monitoring-token-12345")
    assert b"yunsync_http_requests_total" in response.body


def test_metrics_are_hidden_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "monitoring_enabled", False)
    with pytest.raises(HTTPException) as denied:
        metrics("synthetic-monitoring-token-12345")
    assert denied.value.status_code == 404


def test_v2_demo_case_has_two_comparable_synthetic_reports():
    result = validate_demo_case(PROJECT_ROOT / "demo" / "v2_m8_demo_case.json")
    assert result == {
        "valid": True,
        "errors": [],
        "report_count": 2,
        "common_metric_count": 4,
        "synthetic": True,
    }


def test_demo_case_validator_fails_closed_on_malformed_structure(tmp_path):
    manifest = tmp_path / "bad-demo.json"
    manifest.write_text('{"synthetic": true, "reports": [null, {}]}', encoding="utf-8")
    result = validate_demo_case(manifest)
    assert result["valid"] is False
    assert "report_must_be_object" in result["errors"]


def test_release_preflight_separates_engineering_and_external_evidence():
    incomplete = build_release_readiness(_production_settings(), PROJECT_ROOT)
    assert incomplete["engineering_ready"] is True
    assert incomplete["external_acceptance_ready"] is False
    assert incomplete["ready"] is False
    assert "synthetic-monitoring-token" not in json.dumps(incomplete)

    complete = build_release_readiness(
        _production_settings(
            huawei_obs_validation_ref="OBS-ACCEPT-20260923",
            huawei_ocr_validation_ref="OCR-ACCEPT-20260923",
            huawei_maas_validation_ref="MAAS-ACCEPT-20260923",
            release_image_ref="registry.example.com/yunsync:v2@sha256:" + "a" * 64,
            backup_restore_validation_ref="BACKUP-RESTORE-20260923",
            https_validation_ref="HTTPS-ACCEPT-20260923",
            alerting_validation_ref="ALERT-DELIVERY-20260923",
            professional_review_validation_ref="PRO-REVIEW-20260923",
            user_test_validation_ref="USER-TEST-20260923",
            customer_acceptance_validation_ref="CUSTOMER-SIGN-20260923",
        ),
        PROJECT_ROOT,
    )
    assert complete["ready"] is True
    assert "CUSTOMER-SIGN-20260923" not in json.dumps(complete)


def test_release_package_excludes_runtime_secrets_and_has_checksum(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (root / ".env").write_text("SECRET=do-not-package\n", encoding="utf-8")
    (root / "data.db").write_bytes(b"private")
    (root / "backend" / "data").mkdir(parents=True)
    (root / "backend" / "data" / "uploaded-report.pdf").write_bytes(b"private")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "module.js").write_text("ignored", encoding="utf-8")
    (root / "frontend" / ".npm-cache").mkdir(parents=True)
    (root / "frontend" / ".npm-cache" / "cached.tgz").write_bytes(b"ignored")
    monkeypatch.setattr(build_release_package, "PROJECT_ROOT", root)
    monkeypatch.setattr(
        build_release_package,
        "git_value",
        lambda *args: "" if args == ("status", "--porcelain") else "test-value",
    )
    output = root / "release" / "YunSync-test.zip"

    manifest = build_release_package.build_package(output, "test")
    with ZipFile(output) as archive:
        names = set(archive.namelist())
        assert names == {"app.py", "RELEASE_MANIFEST.json"}
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    assert manifest["sha256"] == digest
    assert manifest["working_tree_clean"] is True
    assert output.with_suffix(".zip.sha256").read_text(encoding="ascii").startswith(digest)
