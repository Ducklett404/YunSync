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
