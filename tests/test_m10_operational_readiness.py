import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.alert_rules_check import EXPECTED_ALERTS, validate_rules
from scripts import build_release_package
from scripts.generate_sbom import frontend_components, requirement_names
from scripts import performance_smoke
from scripts.performance_smoke import load_external_tokens, summarize_results
from scripts.staging_acceptance import response_checks, validate_base_url


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_staging_target_requires_clean_https_origin():
    assert validate_base_url("https://staging.example.com/") == "https://staging.example.com"
    assert (
        validate_base_url("http://127.0.0.1:8000", allow_http_local=True)
        == "http://127.0.0.1:8000"
    )
    for unsafe in (
        "http://staging.example.com",
        "https://user:secret@staging.example.com",
        "https://staging.example.com/path",
        "https://staging.example.com?token=secret",
    ):
        with pytest.raises(ValueError):
            validate_base_url(unsafe)


def test_staging_response_gate_requires_status_request_id_and_security_headers():
    headers = {
        "Cache-Control": "private, no-store",
        "Content-Security-Policy": "default-src 'self'",
        "Permissions-Policy": "camera=(), microphone=()",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-Request-ID": "acceptance-01",
    }
    checks = response_checks(
        path="/healthz", status_code=200, headers=headers, expected_status=200
    )
    assert all(item["passed"] for item in checks)
    assert not all(
        item["passed"]
        for item in response_checks(
            path="/healthz", status_code=500, headers={}, expected_status=200
        )
    )


def test_performance_evidence_reports_percentiles_errors_and_throughput():
    result = summarize_results(
        [(200, 10.0), (200, 20.0), (500, 40.0), (200, 30.0)],
        elapsed_seconds=2.0,
    )
    assert result == {
        "requests": 4,
        "status_counts": {"200": 3, "500": 1},
        "error_rate": 0.25,
        "p50_ms": 20.0,
        "p95_ms": 40.0,
        "p99_ms": 40.0,
        "max_ms": 40.0,
        "throughput_rps": 2.0,
    }


def test_external_performance_tokens_must_stay_outside_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = tmp_path / "repository"
    repository.mkdir()
    monkeypatch.setattr(performance_smoke, "PROJECT_ROOT", repository)
    external = tmp_path / "tokens.txt"
    external.write_text("a" * 32 + "\n" + "b" * 32 + "\n", encoding="utf-8")
    assert len(load_external_tokens(external, 2)) == 2
    with pytest.raises(ValueError, match="outside"):
        load_external_tokens(repository / "tokens.txt", 1)


def test_prometheus_alert_baseline_is_complete_and_low_cardinality():
    result = validate_rules(PROJECT_ROOT / "deploy" / "prometheus-alerts.yml")
    assert result == {"status": "passed", "rules": len(EXPECTED_ALERTS), "errors": []}


def test_sbom_inputs_use_direct_python_and_locked_frontend_versions(tmp_path: Path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("fastapi>=0.115,<1\npsycopg[binary]>=3.2\n-r dev.txt\n", encoding="utf-8")
    assert requirement_names(requirements) == ["fastapi", "psycopg"]

    lock = tmp_path / "package-lock.json"
    lock.write_text(
        json.dumps(
            {
                "packages": {
                    "": {"dependencies": {"vue": "^3.5.0"}},
                    "node_modules/vue": {"version": "3.5.42"},
                }
            }
        ),
        encoding="utf-8",
    )
    components, unresolved = frontend_components(lock)
    assert unresolved == []
    assert components[0]["purl"] == "pkg:npm/vue@3.5.42"


def test_ci_and_container_run_m10_supply_chain_gates():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    for marker in (
        "python -m pytest",
        "python -m alembic check",
        "repository_security_scan.py",
        "python -m pip_audit -r requirements.txt",
        "alert_rules_check.py",
        "generate_sbom.py",
        "npm run typecheck",
        "npm run build",
        "npm audit --omit=dev",
    ):
        assert marker in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "SBOM.cdx.json" in dockerfile
    assert "generate_sbom.py" in dockerfile


def test_release_package_embeds_cyclonedx_sbom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = tmp_path / "project"
    (root / "frontend").mkdir(parents=True)
    (root / "requirements.txt").write_text("fastapi>=0.115,<1\n", encoding="utf-8")
    (root / "frontend" / "package-lock.json").write_text(
        json.dumps(
            {
                "packages": {
                    "": {"dependencies": {"vue": "^3.5.0"}},
                    "node_modules/vue": {"version": "3.5.42"},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(build_release_package, "PROJECT_ROOT", root)
    monkeypatch.setattr(
        build_release_package,
        "git_value",
        lambda *args: "" if args == ("status", "--porcelain") else "test-value",
    )
    output = root / "release" / "YunSync-test.zip"

    manifest = build_release_package.build_package(output, "m10-test")

    with ZipFile(output) as archive:
        sbom = json.loads(archive.read("SBOM.cdx.json"))
    assert manifest["sbom_included"] is True
    assert manifest["sbom_unresolved_count"] == 0
    assert sbom["bomFormat"] == "CycloneDX"
    assert {item["name"] for item in sbom["components"]} == {"fastapi", "vue"}
