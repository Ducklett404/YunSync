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


def test_v2_m7_cloud_security_and_external_gates_are_documented_truthfully():
    plan = (PROJECT_ROOT / "docs" / "DEVELOPMENT_PLAN.md").read_text(encoding="utf-8")
    acceptance = (PROJECT_ROOT / "docs" / "V2_M7_ACCEPTANCE.md").read_text(
        encoding="utf-8"
    )
    evaluation = (
        PROJECT_ROOT / "docs" / "V2_M7_SECURITY_MODEL_EVALUATION.md"
    ).read_text(encoding="utf-8")
    runbook = (PROJECT_ROOT / "docs" / "V2_M7_QA_RUNBOOK.md").read_text(
        encoding="utf-8"
    )

    assert "工程门禁已完成" in plan
    assert "真实云联调" in plan
    for adapter in ("OBS", "OCR", "MaaS", "cloud-preflight-v4"):
        assert adapter in acceptance
    for risk in ("对象越权", "提示词攻击", "数值幻觉", "目录外材料"):
        assert risk in evaluation
    for external_gate in ("M7-CLOUD-06", "P01", "P10", "临床营养审核人"):
        assert external_gate in runbook
    assert "本地测试只使用合成数据" in acceptance


def test_week_eight_analysis_review_and_next_step_are_documented():
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
    verification = (PROJECT_ROOT / "docs" / "M8A_VERIFICATION_REPORT.md").read_text(
        encoding="utf-8"
    )
    prompt = (
        PROJECT_ROOT / "backend" / "app" / "prompts" / "result_explanation_v1.md"
    ).read_text(encoding="utf-8")

    assert "里程碑 M8A" in plan
    for acceptance_id in ("AC-07.4", "AC-07.5", "AC-07.6", "AC-07.7"):
        assert acceptance_id in requirements
    for field in ("next_step", "next_step_selected_at"):
        assert field in dictionary
    for contract_item in ("/next-step", "bootstrap_iterations", "policy_fallback"):
        assert contract_item in contract
    assert "result-explain-v1" in prompt
    assert "75 项通过" in verification
    assert "不是华为云 MaaS 成功调用证据" in verification


def test_week_nine_local_cloud_readiness_is_documented_without_fake_cloud_evidence():
    plan = (PROJECT_ROOT / "docs" / "DEVELOPMENT_PLAN.md").read_text(encoding="utf-8")
    environments = (PROJECT_ROOT / "docs" / "ENVIRONMENTS.md").read_text(
        encoding="utf-8"
    )
    runbook = (PROJECT_ROOT / "docs" / "CLOUD_OPERATIONS_RUNBOOK.md").read_text(
        encoding="utf-8"
    )
    verification = (PROJECT_ROOT / "docs" / "M9A_VERIFICATION_REPORT.md").read_text(
        encoding="utf-8"
    )

    assert "里程碑 M9A" in plan
    assert "M9B 的真实 RDS/DCS/IAM" in plan
    for setting in (
        "SEED_DEMO_DATA",
        "CACHE_ENABLED",
        "HUAWEI_CREDENTIAL_MODE",
        "cloud_preflight.py",
    ):
        assert setting in environments
    for evidence in ("空 RDS", "memory_fallback", "--confirm-database", "M9B 证据清单"):
        assert evidence in runbook
    assert "89 项通过" in verification
    assert "不是真实 DCS" in verification
    assert "没有把合成结果冒充真实备份可恢复记录" in verification


def test_week_ten_local_security_performance_is_documented_without_fake_deployment():
    plan = (PROJECT_ROOT / "docs" / "DEVELOPMENT_PLAN.md").read_text(encoding="utf-8")
    environments = (PROJECT_ROOT / "docs" / "ENVIRONMENTS.md").read_text(
        encoding="utf-8"
    )
    runbook = (PROJECT_ROOT / "docs" / "DEPLOYMENT_SECURITY_RUNBOOK.md").read_text(
        encoding="utf-8"
    )
    verification = (PROJECT_ROOT / "docs" / "M10A_VERIFICATION_REPORT.md").read_text(
        encoding="utf-8"
    )

    assert "里程碑 M10A" in plan
    assert "M10B 真实镜像、HTTPS、告警和云端压测仍保持未完成" in plan
    for setting in (
        "ALLOWED_HOSTS",
        "FORWARDED_ALLOW_IPS",
        "FORCE_HTTPS",
        "RATE_LIMIT_ENABLED",
    ):
        assert setting in environments
    for evidence in ("M10B 证据清单", "20 个独立演示账号", "真实日志采集"):
        assert evidence in runbook
    assert "103 passed" in verification
    assert "本机没有 Docker" in verification
    assert "不是 20 名真实用户" in verification


def test_project_license_and_copyright_notice_are_consistent():
    license_text = (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")
    copyright_text = (PROJECT_ROOT / "COPYRIGHT.md").read_text(encoding="utf-8")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    inventory = (PROJECT_ROOT / "docs" / "OPEN_SOURCE_INVENTORY.md").read_text(
        encoding="utf-8"
    )

    assert license_text.startswith("MIT License\n\nCopyright (c) 2026 YunSync Contributors")
    for clause in (
        "Permission is hereby granted, free of charge",
        "The above copyright notice and this permission notice shall be included",
        'THE SOFTWARE IS PROVIDED "AS IS"',
    ):
        assert clause in license_text
    assert "[MIT License](LICENSE)" in copyright_text
    assert "[MIT License](LICENSE)" in readme
    assert "[MIT License](../LICENSE)" in inventory
