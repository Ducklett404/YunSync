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


def test_week_five_action_governance_is_documented_without_fake_reviews():
    plan = (PROJECT_ROOT / "docs" / "DEVELOPMENT_PLAN.md").read_text(encoding="utf-8")
    dictionary = (PROJECT_ROOT / "docs" / "DATA_DICTIONARY.md").read_text(encoding="utf-8")
    contract = (PROJECT_ROOT / "docs" / "API_CONTRACT.md").read_text(encoding="utf-8")
    register = (PROJECT_ROOT / "docs" / "ACTION_TEMPLATE_REGISTER.md").read_text(
        encoding="utf-8"
    )
    verification = (PROJECT_ROOT / "docs" / "M5A_VERIFICATION_REPORT.md").read_text(
        encoding="utf-8"
    )
    prompt = (
        PROJECT_ROOT / "backend" / "app" / "prompts" / "action_explanation_v1.md"
    ).read_text(encoding="utf-8")

    assert "里程碑 M5A" in plan
    assert "专业审核和真实 MaaS 接入仍保持未完成" in plan
    for field in ("review_status", "review_scope", "is_active", "ranking_policy_version"):
        assert field in dictionary
    for route in (
        "/api/v1/admin/action-templates",
        "/versions",
        "/status",
        "score_components",
    ):
        assert route in contract
    for template_id in ("action-walk-10", "action-water-swap", "action-veg-first"):
        assert template_id in register
    assert "不是医学、营养或运动专业审核" in register
    assert "action-explain-v1" in prompt
    for forbidden_topic in ("确诊", "停药", "极端节食", "疗效承诺"):
        assert forbidden_topic in prompt
    assert "57 项通过" in verification
    assert "不以合成结果替代" in verification


def test_week_six_experiment_state_machine_and_schedule_lock_are_documented():
    plan = (PROJECT_ROOT / "docs" / "DEVELOPMENT_PLAN.md").read_text(encoding="utf-8")
    requirements = (PROJECT_ROOT / "docs" / "PRODUCT_REQUIREMENTS.md").read_text(
        encoding="utf-8"
    )
    dictionary = (PROJECT_ROOT / "docs" / "DATA_DICTIONARY.md").read_text(
        encoding="utf-8"
    )
    contract = (PROJECT_ROOT / "docs" / "API_CONTRACT.md").read_text(
        encoding="utf-8"
    )
    verification = (PROJECT_ROOT / "docs" / "M6A_VERIFICATION_REPORT.md").read_text(
        encoding="utf-8"
    )

    assert "里程碑 M6A" in plan
    for acceptance_id in ("AC-05.4", "AC-05.5", "AC-05.6", "AC-06.2"):
        assert acceptance_id in requirements
    for field in (
        "schedule_version",
        "schedule_hash",
        "schedule_locked_at",
        "completed_at",
        "uq_experiments_active_user",
    ):
        assert field in dictionary
    for route in ("/pause", "/resume", "/terminate", "/complete"):
        assert route in contract
    assert "63 项通过" in verification
    assert "没有用仿真记录替代外部验收" in verification


def test_week_seven_daily_records_reminders_and_import_are_documented():
    plan = (PROJECT_ROOT / "docs" / "DEVELOPMENT_PLAN.md").read_text(encoding="utf-8")
    requirements = (PROJECT_ROOT / "docs" / "PRODUCT_REQUIREMENTS.md").read_text(
        encoding="utf-8"
    )
    dictionary = (PROJECT_ROOT / "docs" / "DATA_DICTIONARY.md").read_text(
        encoding="utf-8"
    )
    contract = (PROJECT_ROOT / "docs" / "API_CONTRACT.md").read_text(
        encoding="utf-8"
    )
    verification = (PROJECT_ROOT / "docs" / "M7A_VERIFICATION_REPORT.md").read_text(
        encoding="utf-8"
    )

    assert "里程碑 M7A" in plan
    for acceptance_id in ("AC-06.5", "AC-06.6", "AC-06.7", "AC-06.8"):
        assert acceptance_id in requirements
    for field in (
        "reminder_enabled",
        "reminder_time",
        "discomfort_level",
        "unplanned_event",
    ):
        assert field in dictionary
    for route in ("/observations/template", "/observations/import"):
        assert route in contract
    assert "68 项通过" in verification
    assert "未伪造移动端浏览器走查记录" in verification
