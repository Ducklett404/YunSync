from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_week_one_documents_and_requirement_ids_exist():
    requirements = (PROJECT_ROOT / "docs" / "PRODUCT_REQUIREMENTS.md").read_text(encoding="utf-8")
    flow = (PROJECT_ROOT / "docs" / "UX_FLOW.md").read_text(encoding="utf-8")
    copy = (PROJECT_ROOT / "docs" / "CONTENT_COPY.md").read_text(encoding="utf-8")
    usability = (PROJECT_ROOT / "docs" / "USABILITY_TEST_PLAN.md").read_text(encoding="utf-8")
    simulation = (PROJECT_ROOT / "docs" / "USABILITY_SIMULATION_REPORT.md").read_text(encoding="utf-8")

    for story_number in range(1, 9):
        assert f"US-{story_number:02d}" in requirements
    for route in ("/start", "/report", "/actions", "/experiment", "/results"):
        assert route in flow
    for copy_number in range(1, 13):
        assert f"CP-{copy_number:02d}" in copy
    for task_number in range(1, 6):
        assert f"T-{task_number:02d}" in usability
    for persona_number in range(1, 6):
        assert f"P{persona_number:02d}" in simulation
    assert "不是 3 至 5 名真实同学的可用性测试" in simulation


def test_onboarding_prototype_is_registered():
    router = (PROJECT_ROOT / "frontend" / "src" / "router" / "index.ts").read_text(encoding="utf-8")
    onboarding = (PROJECT_ROOT / "frontend" / "src" / "views" / "OnboardingView.vue").read_text(encoding="utf-8")
    access_state = (PROJECT_ROOT / "frontend" / "src" / "state" / "onboarding.ts").read_text(encoding="utf-8")

    assert "path: '/start'" in router
    assert "requiresOnboarding: true" in router
    assert "canAccessHealthFlow()" in router
    assert "不提供疾病诊断、治疗、处方或药物调整意见" in onboarding
    assert "hasSafetyFlag" in onboarding
    assert "unlockHealthFlow()" in onboarding
    assert "healthFlowUnlocked = false" in access_state


def test_week_two_engineering_documents_and_templates_exist():
    architecture = (PROJECT_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    dictionary = (PROJECT_ROOT / "docs" / "DATA_DICTIONARY.md").read_text(encoding="utf-8")
    contract = (PROJECT_ROOT / "docs" / "API_CONTRACT.md").read_text(encoding="utf-8")
    environments = (PROJECT_ROOT / "docs" / "ENVIRONMENTS.md").read_text(encoding="utf-8")
    verification = (PROJECT_ROOT / "docs" / "M2A_VERIFICATION_REPORT.md").read_text(encoding="utf-8")

    assert "X-Request-ID" in architecture
    for table_name in (
        "user_profiles",
        "health_reports",
        "health_metrics",
        "action_templates",
        "experiments",
        "observations",
        "audit_logs",
    ):
        assert table_name in dictionary
    for route in (
        "/healthz",
        "/readyz",
        "/api/v1/dashboard",
        "/api/v1/reports/analyze",
        "/api/v1/experiments",
        "/observations",
    ):
        assert route in contract
    assert "X-Request-ID" in contract
    for template_name in (".env.local.example", ".env.devspace.example", ".env.staging.example"):
        assert template_name in environments
        assert (PROJECT_ROOT / template_name).is_file()
    assert "23 项通过" in verification
    assert "没有安装 Docker" in verification
    assert "不以模拟结果替代" in verification


def test_week_three_identity_consent_and_profile_are_documented():
    plan = (PROJECT_ROOT / "docs" / "DEVELOPMENT_PLAN.md").read_text(encoding="utf-8")
    dictionary = (PROJECT_ROOT / "docs" / "DATA_DICTIONARY.md").read_text(encoding="utf-8")
    contract = (PROJECT_ROOT / "docs" / "API_CONTRACT.md").read_text(encoding="utf-8")
    verification = (PROJECT_ROOT / "docs" / "M3A_VERIFICATION_REPORT.md").read_text(
        encoding="utf-8"
    )
    router = (PROJECT_ROOT / "frontend" / "src" / "router" / "index.ts").read_text(
        encoding="utf-8"
    )

    assert "里程碑 M3A" in plan
    assert "当前不伪造完成" in plan
    for table_name in ("auth_sessions", "consent_records", "screening_answers"):
        assert table_name in dictionary
    for route in (
        "/api/v1/auth/demo",
        "/api/v1/consents/withdraw",
        "/api/v1/profile/screening",
        "/api/v1/admin/audit-events",
    ):
        assert route in contract
    assert "path: '/profile'" in router
    assert "32 项通过" in verification
    assert "不以合成记录替代" in verification


def test_week_four_report_workflow_is_documented_without_fake_cloud_claims():
    plan = (PROJECT_ROOT / "docs" / "DEVELOPMENT_PLAN.md").read_text(encoding="utf-8")
    dictionary = (PROJECT_ROOT / "docs" / "DATA_DICTIONARY.md").read_text(encoding="utf-8")
    contract = (PROJECT_ROOT / "docs" / "API_CONTRACT.md").read_text(encoding="utf-8")
    evaluation = (PROJECT_ROOT / "docs" / "OCR_EVALUATION_REPORT.md").read_text(
        encoding="utf-8"
    )
    verification = (PROJECT_ROOT / "docs" / "M4A_VERIFICATION_REPORT.md").read_text(
        encoding="utf-8"
    )

    assert "里程碑 M4A" in plan
    assert "真实 OBS 与真实 OCR 接入仍保持未完成" in plan
    for field in ("ocr_status", "confidence", "source_bbox", "review_status"):
        assert field in dictionary
    for route in ("/retry", "/source", "/metrics/{metric_id}/confirm"):
        assert route in contract
    for scenario in ("standard", "blurred", "rotated", "low_resolution", "timeout", "failure"):
        assert scenario in evaluation
    assert "45 项通过" in verification
    assert "不是 OBS 成功证据" in verification
