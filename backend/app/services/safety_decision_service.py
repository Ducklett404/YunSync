"""Conservative preliminary triage; no clinical metric thresholds are encoded."""

from sqlalchemy.orm import Session

from app.models.user import UserProfile
from app.repositories.health_repository import health_repository
from app.schemas.safety_decision import SafetyDecisionOut
from app.services.food_safety_service import get_food_safety_profile


RULE_VERSION = "v2-safety-preliminary-2"

MISSING_LABELS = (
    ("allergy_status", "食物或原料过敏"),
    ("medication_status", "正在用药"),
    ("condition_status", "已知疾病或健康状况"),
    ("clinician_restriction_status", "医生提出的饮食限制"),
    ("special_status", "孕哺或其他特殊状态"),
)


def evaluate_safety(db: Session, user: UserProfile) -> SafetyDecisionOut:
    # A self-reported acute symptom has priority even when other information is missing.
    if user.screening_answers.get("acute_symptoms") is True:
        return SafetyDecisionOut(
            decision="urgent_care",
            tier="C",
            can_generate_plan=False,
            rule_version=RULE_VERSION,
            message="你报告了可能需要紧急处理的症状。若症状正在发生，请及时联系当地急救服务；系统不能判断具体病因。",
            missing_items=[],
        )

    report = health_repository.latest_report(db, user.id)
    if report is not None and report.critical_marker_status == "yes":
        return SafetyDecisionOut(
            decision="urgent_care",
            tier="C",
            can_generate_plan=False,
            rule_version=RULE_VERSION,
            message="你确认报告标注了危急值。请尽快联系出具报告的机构或医生核实并获得指导；系统不能判断具体病因。",
            missing_items=[],
        )

    profile = get_food_safety_profile(db, user)
    if profile.readiness == "needs_professional_review":
        return SafetyDecisionOut(
            decision="consult_professional",
            tier="B",
            can_generate_plan=False,
            rule_version=RULE_VERSION,
            message="当前资料提示需要先咨询医生或营养专业人员，暂不提供自动食养方案。",
            missing_items=[],
        )

    missing: list[str] = []
    if user.screening_status != "eligible":
        missing.append("安全初筛")
    for field, label in MISSING_LABELS:
        if getattr(profile, field) == "unknown":
            missing.append(label)

    if report is None:
        missing.append("体检报告")
    else:
        if report.critical_marker_status == "unknown":
            missing.append("报告危急标记确认")
        metrics = health_repository.metrics_for_report(db, report.id)
        if report.status != "confirmed" or not metrics or any(not metric.confirmed for metric in metrics):
            missing.append("报告逐项确认")

    if missing:
        return SafetyDecisionOut(
            decision="complete_information",
            tier=None,
            can_generate_plan=False,
            rule_version=RULE_VERSION,
            message="请先补齐并确认资料。未回答的风险信息不能视为没有风险。",
            missing_items=missing,
        )

    return SafetyDecisionOut(
        decision="awaiting_review_rules",
        tier=None,
        can_generate_plan=False,
        rule_version=RULE_VERSION,
        message="资料已准备，但食材、食谱和安全规则尚未完成专业审核，暂不能生成方案。",
        missing_items=[],
    )
