"""M6 execution records, user-sourced reminders, and report-led revisions."""

import hashlib
import json
from collections import Counter
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.care_plan import AdherenceLog, CarePlan, FollowUpReminder, PlanRevision
from app.models.user import UserProfile
from app.repositories.health_repository import health_repository
from app.schemas.care_plan import AdherenceLogIn, CarePlanRequest, ReminderIn
from app.services.care_plan_service import CarePlanConflict, care_plan_service
from app.services.follow_up_service import FollowUpConflict, compare_reports


def owned_plan(db: Session, user: UserProfile, plan_id: str) -> CarePlan:
    plan = db.get(CarePlan, plan_id)
    if plan is None or plan.user_id != user.id:
        raise LookupError("方案不存在")
    return plan


def list_logs(db: Session, user: UserProfile, plan_id: str) -> list[AdherenceLog]:
    owned_plan(db, user, plan_id)
    return list(db.scalars(select(AdherenceLog).where(
        AdherenceLog.plan_id == plan_id, AdherenceLog.user_id == user.id,
    ).order_by(AdherenceLog.day)))


def record_log(
    db: Session, user: UserProfile, plan_id: str, day: int, payload: AdherenceLogIn
) -> AdherenceLog:
    if day < 1 or day > 7:
        raise CarePlanConflict("执行日期必须在方案的 7 天安排内")
    plan = owned_plan(db, user, plan_id)
    if payload.status == "replaced" and not payload.replacement:
        raise CarePlanConflict("记录替换时请填写实际替换内容；此记录不代表系统推荐")
    if payload.status != "replaced" and payload.replacement:
        raise CarePlanConflict("只有替换记录可填写替换内容")
    existing = db.scalar(select(AdherenceLog).where(
        AdherenceLog.plan_id == plan_id, AdherenceLog.day == day,
    ))
    values = payload.model_dump()
    if existing is not None and all(getattr(existing, key) == value for key, value in values.items()):
        return existing
    if existing is not None and existing.discomfort and not payload.discomfort:
        raise CarePlanConflict("已记录的不适不能自行撤销；请先寻求专业评估")
    # Refresh the live gate before accepting a daily action.
    care_plan_service.current(db, user)
    db.refresh(plan)
    if plan.status != "ACTIVE":
        raise CarePlanConflict("当前方案已暂停或不是活动方案，不能继续记录执行")
    scheduled = plan.snapshot["schedule"][day - 1]
    if date.fromisoformat(scheduled["date"]) > date.today():
        raise CarePlanConflict("不能提前填写未来日期的执行记录")
    log = existing or AdherenceLog(user_id=user.id, plan_id=plan_id, day=day)
    for key, value in values.items():
        setattr(log, key, value)
    log.updated_at = datetime.now(timezone.utc)
    db.add(log)
    if payload.discomfort:
        plan.status = "PAUSED"
        plan.pause_reason = "adverse_feedback"
        plan.paused_at = datetime.now(timezone.utc)
    db.add(AuditLog(event_type="care_plan.feedback", actor_id=user.id, payload={
        "plan_id": plan_id, "day": day, "status": payload.status,
        "discomfort": payload.discomfort,
    }))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise CarePlanConflict("执行记录发生并发变化，请刷新后重试") from exc
    db.refresh(log)
    return log


def get_reminder(db: Session, user: UserProfile, plan_id: str) -> FollowUpReminder | None:
    owned_plan(db, user, plan_id)
    return db.scalar(select(FollowUpReminder).where(
        FollowUpReminder.plan_id == plan_id, FollowUpReminder.user_id == user.id,
    ))


def set_reminder(
    db: Session, user: UserProfile, plan_id: str, payload: ReminderIn
) -> FollowUpReminder:
    plan = owned_plan(db, user, plan_id)
    existing = get_reminder(db, user, plan_id)
    values = payload.model_dump()
    if existing is not None and all(getattr(existing, key) == value for key, value in values.items()):
        return existing
    if plan.status == "SUPERSEDED":
        raise CarePlanConflict("历史方案的复查提醒不能修改")
    if payload.enabled and payload.remind_on < date.today():
        raise CarePlanConflict("启用的提醒日期不能早于今天")
    if payload.basis in {"doctor", "report"} and not payload.note:
        raise CarePlanConflict("请选择医生或报告依据时，请简述该日期的来源")
    reminder = existing or FollowUpReminder(user_id=user.id, plan_id=plan_id)
    for key, value in values.items():
        setattr(reminder, key, value)
    reminder.updated_at = datetime.now(timezone.utc)
    db.add(reminder)
    db.add(AuditLog(event_type="care_plan.reminder_set", actor_id=user.id, payload={
        "plan_id": plan_id, "basis": payload.basis, "enabled": payload.enabled,
    }))
    db.commit()
    db.refresh(reminder)
    return reminder


def _adherence_summary(db: Session, old: CarePlan) -> dict:
    logs = list(db.scalars(select(AdherenceLog).where(
        AdherenceLog.plan_id == old.id, AdherenceLog.user_id == old.user_id,
    )))
    counts = Counter(log.status for log in logs)
    return {
        "scheduled_days": len(old.snapshot["schedule"]),
        "logged_days": len(logs),
        "completed_days": counts["completed"],
        "skipped_days": counts["skipped"],
        "replaced_days": counts["replaced"],
        "discomfort_recorded": any(log.discomfort for log in logs),
        "limitation": "执行记录只作为新方案的可执行性背景，不用于归因指标变化或推断食谱疗效。",
    }


def _change_log(old: CarePlan, new: CarePlan, adherence: dict) -> list[dict]:
    old_snapshot, new_snapshot = old.snapshot, new.snapshot
    old_counts = Counter((day["recipe_code"], day["recipe_version"]) for day in old_snapshot["schedule"])
    new_counts = Counter((day["recipe_code"], day["recipe_version"]) for day in new_snapshot["schedule"])
    old_recipes = {(item["code"], item["version"]): item for item in old_snapshot["recipes"]}
    new_recipes = {(item["code"], item["version"]): item for item in new_snapshot["recipes"]}
    changes = []
    reason = "根据新报告中已确认的目标及当前约束重新匹配审核模板；不推断食谱疗效。"
    changes.append({
        "type": "continued", "subject": "旧方案执行背景",
        "reason": (
            f"已记录 {adherence['logged_days']}/{adherence['scheduled_days']} 天："
            f"完成 {adherence['completed_days']}、跳过 {adherence['skipped_days']}、"
            f"自行替换 {adherence['replaced_days']}。记录仅用于核对可执行性，不归因指标变化。"
        ),
    })
    old_goals = {goal["code"] for goal in old_snapshot["goals"]}
    new_goals = {goal["code"] for goal in new_snapshot["goals"]}
    for code in sorted(old_goals & new_goals):
        changes.append({"type": "continued", "subject": f"关注指标 {code}",
                        "reason": "该指标在新报告中仍经用户确认；不据单次数值判断效果。"})
    for code in sorted(old_goals - new_goals):
        changes.append({"type": "paused", "subject": f"关注指标 {code}",
                        "reason": "本期未选为目标；不表示该指标已恢复正常。"})
    for code in sorted(new_goals - old_goals):
        changes.append({"type": "added", "subject": f"关注指标 {code}",
                        "reason": "新报告中已确认并由用户选作本期目标。"})
    for ref in sorted(old_recipes.keys() & new_recipes.keys()):
        old_count = old_counts[ref]
        new_count = new_counts[ref]
        change_type = (
            "reduced" if new_count < old_count
            else "increased" if new_count > old_count
            else "continued"
        )
        changes.append({
            "type": change_type,
            "subject": f"{ref[0]}@{ref[1]}（周安排 {old_count} → {new_count} 次）",
            "reason": reason,
        })
    removed = sorted(old_recipes.keys() - new_recipes.keys())
    added = sorted(new_recipes.keys() - old_recipes.keys())
    for day, (old_day, new_day) in enumerate(zip(old_snapshot["schedule"], new_snapshot["schedule"]), 1):
        old_ref = (old_day["recipe_code"], old_day["recipe_version"])
        new_ref = (new_day["recipe_code"], new_day["recipe_version"])
        if old_ref != new_ref:
            changes.append({
                "type": "replaced", "subject": f"第 {day} 天：{old_ref[0]}@{old_ref[1]} → {new_ref[0]}@{new_ref[1]}",
                "reason": "该日的示例餐食在新方案中重新安排；不推断食谱疗效。",
            })
    for ref in removed:
        changes.append({"type": "paused", "subject": f"{ref[0]}@{ref[1]}", "reason": reason})
    for ref in added:
        changes.append({"type": "added", "subject": f"{ref[0]}@{ref[1]}", "reason": reason})
    return changes


def revise_plan(
    db: Session, user: UserProfile, old_plan_id: str, request: CarePlanRequest
) -> CarePlan:
    old = owned_plan(db, user, old_plan_id)
    if old.pause_reason == "adverse_feedback":
        raise CarePlanConflict("曾记录不适，不能自动生成新方案；请先寻求专业评估")
    latest = health_repository.latest_report(db, user.id)
    if latest is None or latest.id == old.report_id:
        raise CarePlanConflict("尚无新报告，请先上传并确认复查报告")
    if latest.status != "confirmed":
        raise CarePlanConflict("新报告尚未完成整份核对")
    care_plan_service.current(db, user)
    db.refresh(old)
    if old.status not in {"PAUSED", "SUPERSEDED"}:
        raise CarePlanConflict("旧方案需先因新报告暂停，才能生成修订版本")
    try:
        comparison = compare_reports(db, user.id, old.report_id, latest.id)
    except FollowUpConflict as exc:
        raise CarePlanConflict(str(exc)) from exc
    adherence = _adherence_summary(db, old)
    snapshot = care_plan_service.build_snapshot(db, user, request)
    if snapshot.report_id != latest.id:
        raise CarePlanConflict("方案与最新报告不一致，请刷新后重试")
    data = snapshot.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    existing = db.scalar(select(CarePlan).where(
        CarePlan.user_id == user.id, CarePlan.request_hash == digest,
    ))
    if existing is not None:
        if existing.previous_plan_id == old.id:
            return existing
        raise CarePlanConflict("相同方案已由其他版本生成，请查看方案历史")
    prior_revision = db.scalar(select(PlanRevision).where(PlanRevision.old_plan_id == old.id))
    if prior_revision is not None:
        raise CarePlanConflict("旧方案已有修订草案，请查看当前版本")
    if old.status == "SUPERSEDED":
        raise CarePlanConflict("旧方案已被新版本替代，请基于当前方案继续复查")
    active = db.scalar(select(CarePlan).where(
        CarePlan.user_id == user.id, CarePlan.status == "ACTIVE",
    ))
    if active is not None:
        raise CarePlanConflict("已有活动方案，请先处理当前方案")
    new = CarePlan(
        user_id=user.id, report_id=latest.id, status="READY", request_hash=digest,
        snapshot=data, previous_plan_id=old.id, version=old.version + 1,
    )
    db.add(new)
    db.flush()
    revision = PlanRevision(
        user_id=user.id, old_plan_id=old.id, new_plan_id=new.id,
        new_report_id=latest.id, changes=_change_log(old, new, adherence),
        comparison={**comparison.model_dump(mode="json"), "adherence_summary": adherence},
    )
    db.add(revision)
    db.add(AuditLog(event_type="care_plan.revised", actor_id=user.id, payload={
        "old_plan_id": old.id, "new_plan_id": new.id, "new_report_id": latest.id,
    }))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise CarePlanConflict("方案版本发生并发变化，请刷新后重试") from exc
    db.refresh(new)
    return new


def get_revision(db: Session, user: UserProfile, new_plan_id: str) -> PlanRevision | None:
    owned_plan(db, user, new_plan_id)
    return db.scalar(select(PlanRevision).where(
        PlanRevision.new_plan_id == new_plan_id, PlanRevision.user_id == user.id,
    ))
