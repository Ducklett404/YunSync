from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.core.cloud_readiness import build_cloud_readiness
from app.core.config import Settings
from app.core.demo_case import validate_demo_case


M8_RELEASE_PREFLIGHT_VERSION = "m8-release-preflight-v1"
IMAGE_DIGEST_PATTERN = re.compile(r"^[^\s@]+@sha256:[0-9a-fA-F]{64}$")
REQUIRED_DOCUMENTS = (
    "docs/USER_GUIDE.md",
    "docs/ADMIN_GUIDE.md",
    "docs/PRIVACY_NOTICE.md",
    "docs/CONTENT_OPERATIONS_RUNBOOK.md",
    "docs/INCIDENT_RESPONSE_RUNBOOK.md",
    "docs/V2_PROFESSIONAL_REVIEW_RECORD.md",
    "docs/V2_M8_ACCEPTANCE.md",
    "docs/V2_M8_CUSTOMER_ACCEPTANCE.md",
)


def _has_evidence_ref(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        len(normalized) >= 8
        and "change_me" not in normalized
        and normalized not in {"pending", "placeholder", "unknown"}
        and not normalized.startswith(("replace-", "replace_"))
    )


def _check(code: str, passed: bool, category: str, guidance: str) -> dict[str, Any]:
    return {"code": code, "passed": passed, "category": category, "guidance": guidance}


def build_release_readiness(settings: Settings, project_root: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    cloud_report = build_cloud_readiness(settings)
    cloud_engineering_checks = [
        item for item in cloud_report["checks"] if item["code"] != "provider_live_acceptance"
    ]
    demo_case = validate_demo_case(project_root / "demo" / "v2_m8_demo_case.json")
    documents_present = all((project_root / item).is_file() for item in REQUIRED_DOCUMENTS)
    engineering_checks = [
        _check(
            "cloud_configuration",
            all(item["passed"] for item in cloud_engineering_checks),
            "engineering",
            "云端配置、适配器和生产安全项必须通过；真实调用证据单独验收。",
        ),
        _check(
            "monitoring_endpoint",
            settings.monitoring_enabled
            and len(settings.monitoring_token) >= 24
            and not settings._is_placeholder(settings.monitoring_token),
            "engineering",
            "必须启用受令牌保护、只输出聚合值的监控端点。",
        ),
        _check(
            "deployment_assets",
            all(
                (project_root / item).is_file()
                for item in (
                    "Dockerfile",
                    "docker-compose.yml",
                    "deploy/nginx.conf.example",
                    "scripts/postgres_ops.py",
                    "scripts/build_release_package.py",
                )
            ),
            "engineering",
            "镜像、迁移/备份、HTTPS 和发布包工具必须存在。",
        ),
        _check(
            "v2_demo_case",
            bool(demo_case["valid"]),
            "engineering",
            "双报告合成案例必须通过结构、可比性和脱敏校验。",
        ),
        _check(
            "delivery_documents",
            documents_present,
            "engineering",
            "用户、管理员、隐私、内容运营、事故响应和验收文档必须齐全。",
        ),
    ]
    external_checks = [
        _check(
            "provider_live_acceptance",
            next(
                item["passed"]
                for item in cloud_report["checks"]
                if item["code"] == "provider_live_acceptance"
            ),
            "external",
            "需要 OBS、OCR、MaaS 真实脱敏联调记录。",
        ),
        _check(
            "immutable_image",
            bool(IMAGE_DIGEST_PATTERN.fullmatch(settings.release_image_ref.strip())),
            "external",
            "发布镜像必须记录 tag 和不可变 sha256 digest。",
        ),
        _check("backup_restore_drill", _has_evidence_ref(settings.backup_restore_validation_ref), "external", "需要备份恢复演练记录。"),
        _check("https_validation", _has_evidence_ref(settings.https_validation_ref), "external", "需要正式域名 HTTPS 验收记录。"),
        _check("alert_delivery", _has_evidence_ref(settings.alerting_validation_ref), "external", "需要告警规则和送达演练记录。"),
        _check("professional_review", _has_evidence_ref(settings.professional_review_validation_ref), "external", "需要专业人员审核签署编号。"),
        _check("user_test", _has_evidence_ref(settings.user_test_validation_ref), "external", "需要 5–10 名目标用户测试记录。"),
        _check("customer_acceptance", _has_evidence_ref(settings.customer_acceptance_validation_ref), "external", "需要客户验收签收编号。"),
    ]
    checks = engineering_checks + external_checks
    return {
        "version": M8_RELEASE_PREFLIGHT_VERSION,
        "environment": settings.environment,
        "engineering_ready": all(item["passed"] for item in engineering_checks),
        "external_acceptance_ready": all(item["passed"] for item in external_checks),
        "ready": all(item["passed"] for item in checks),
        "checks": checks,
        "summary": {
            "passed": sum(1 for item in checks if item["passed"]),
            "total": len(checks),
            "demo_case_valid": bool(demo_case["valid"]),
            "required_documents_present": documents_present,
            "image_digest_recorded": bool(
                IMAGE_DIGEST_PATTERN.fullmatch(settings.release_image_ref.strip())
            ),
        },
    }
