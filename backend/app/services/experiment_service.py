from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.action_policy import template_is_publishable
from app.core.config import settings
from app.core.experiment_policy import (
    SCHEDULE_VERSION,
    build_schedule,
    schedule_digest,
    validate_locked_schedule,
)
from app.models.action import ActionTemplate
from app.models.audit import AuditLog
from app.models.experiment import Experiment, Observation
from app.models.user import UserProfile
from app.repositories.experiment_repository import experiment_repository
from app.repositories.health_repository import health_repository
from app.schemas.experiment import ExperimentTransition, ObservationCreate


RESULT_METRICS = {
    "postmeal_walk": ("steps_30m", "饭后 30 分钟步数", "步", "higher"),
    "drink_swap": ("sugary_drinks", "含糖饮料次数", "次", "lower"),
    "meal_order": ("subjective_score", "餐后状态评分", "分", "higher"),
}

STATUS_LABELS = {
    "active": "进行中",
    "paused": "已暂停",
    "terminated": "已终止",
    "completed": "已完成",
}

TRANSITION_TARGETS: dict[str, dict[ExperimentTransition, str]] = {
    "active": {
        "pause": "paused",
        "terminate": "terminated",
        "complete": "completed",
    },
    "paused": {
        "resume": "active",
        "terminate": "terminated",
        "complete": "completed",
    },
    "terminated": {},
    "completed": {},
}


class ExperimentConflictError(RuntimeError):
    pass


class ExperimentStateError(ValueError):
    pass


class ExperimentService:
    def create(
        self,
        db: Session,
        user_id: str,
        action_id: str,
        start_date: date | None,
    ) -> Experiment:
        user = db.get(UserProfile, user_id)
        action = db.get(ActionTemplate, action_id)
        if user is None:
            raise LookupError("用户不存在")
        if action is None:
            raise LookupError("行动模板不存在")
        self._validate_prerequisites(db, user, action)

        now = datetime.now(timezone.utc)
        for active in experiment_repository.active_for_user(db, user_id):
            self.ensure_schedule_integrity(active)
            active.status = "paused"
            active.paused_at = now
            active.updated_at = now
            db.add(
                AuditLog(
                    event_type="experiment.paused",
                    actor_id=user_id,
                    payload={
                        "experiment_id": active.id,
                        "from_status": "active",
                        "to_status": "paused",
                        "reason": "replaced_by_new_experiment",
                    },
                )
            )
        db.flush()

        start = start_date or date.today()
        end = start + timedelta(days=13)
        seed = random.SystemRandom().randint(100000, 999999)
        schedule = build_schedule(start, seed)
        experiment = Experiment(
            user_id=user_id,
            action_id=action_id,
            start_date=start,
            end_date=end,
            randomization_seed=seed,
            schedule=schedule,
            schedule_version=SCHEDULE_VERSION,
            schedule_hash=schedule_digest(
                schedule=schedule,
                start_date=start,
                end_date=end,
                seed=seed,
            ),
            schedule_locked_at=now,
            started_at=now,
            updated_at=now,
            status="active",
        )
        db.add(experiment)
        try:
            db.flush()
            db.add(
                AuditLog(
                    event_type="experiment.started",
                    actor_id=user_id,
                    payload={
                        "experiment_id": experiment.id,
                        "action_id": action_id,
                        "seed": seed,
                        "schedule_version": SCHEDULE_VERSION,
                    },
                )
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ExperimentConflictError("当前已有进行中的实验，请刷新后重试") from exc
        db.refresh(experiment)
        return experiment

    def snapshot(self, db: Session, experiment: Experiment) -> dict:
        self.ensure_schedule_integrity(experiment)
        action = db.get(ActionTemplate, experiment.action_id)
        observations = experiment_repository.observations(db, experiment.id)
        by_date = {item.observed_on.isoformat(): item for item in observations}
        schedule = [
            {
                **day,
                "recorded": day["date"] in by_date,
                "completed": bool(by_date[day["date"]].completed)
                if day["date"] in by_date
                else False,
            }
            for day in experiment.schedule
        ]
        recorded_days = len(observations)
        completed_days = sum(item.completed for item in observations)
        return {
            "id": experiment.id,
            "user_id": experiment.user_id,
            "action_id": experiment.action_id,
            "action_code": action.code if action else "unknown",
            "action_title": action.title if action else "未知行动",
            "primary_metric": action.primary_metric if action else "未知指标",
            "status": experiment.status,
            "status_label": STATUS_LABELS.get(experiment.status, experiment.status),
            "start_date": experiment.start_date,
            "end_date": experiment.end_date,
            "randomization_seed": experiment.randomization_seed,
            "schedule_version": experiment.schedule_version,
            "schedule_locked_at": experiment.schedule_locked_at,
            "started_at": experiment.started_at,
            "paused_at": experiment.paused_at,
            "terminated_at": experiment.terminated_at,
            "completed_at": experiment.completed_at,
            "progress": recorded_days,
            "recorded_days": recorded_days,
            "completed_days": completed_days,
            "allowed_transitions": self.allowed_transitions(db, experiment),
            "schedule": schedule,
        }

    def transition(
        self,
        db: Session,
        experiment_id: str,
        transition: ExperimentTransition,
        actor_id: str,
    ) -> Experiment:
        experiment = experiment_repository.get(db, experiment_id)
        if experiment is None:
            raise LookupError("实验不存在")
        self.ensure_schedule_integrity(experiment)
        target = TRANSITION_TARGETS.get(experiment.status, {}).get(transition)
        if target is None:
            raise ExperimentStateError(
                f"实验状态“{STATUS_LABELS.get(experiment.status, experiment.status)}”不允许执行该操作"
            )
        if target == "active":
            other_active = [
                item
                for item in experiment_repository.active_for_user(db, experiment.user_id)
                if item.id != experiment.id
            ]
            if other_active:
                raise ExperimentConflictError("当前已有其他进行中的实验，不能恢复此实验")
        if target == "completed" and not self._completion_ready(db, experiment):
            raise ExperimentStateError("需到达第 14 天并完成 14 天记录后才能结束实验")

        previous = experiment.status
        now = datetime.now(timezone.utc)
        experiment.status = target
        experiment.updated_at = now
        if target == "active":
            experiment.paused_at = None
        elif target == "paused":
            experiment.paused_at = now
        elif target == "terminated":
            experiment.terminated_at = now
        elif target == "completed":
            experiment.completed_at = now

        event_type = (
            "experiment.paused"
            if transition == "pause"
            else f"experiment.{transition}d"
        )
        db.add(
            AuditLog(
                event_type=event_type,
                actor_id=actor_id,
                payload={
                    "experiment_id": experiment.id,
                    "from_status": previous,
                    "to_status": target,
                },
            )
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ExperimentConflictError("状态更新与另一个活动实验冲突") from exc
        db.refresh(experiment)
        return experiment

    def allowed_transitions(self, db: Session, experiment: Experiment) -> list[str]:
        actions = list(TRANSITION_TARGETS.get(experiment.status, {}))
        if "complete" in actions and not self._completion_ready(db, experiment):
            actions.remove("complete")
        return actions

    @staticmethod
    def ensure_schedule_integrity(experiment: Experiment) -> None:
        validate_locked_schedule(
            schedule=experiment.schedule,
            start_date=experiment.start_date,
            end_date=experiment.end_date,
            seed=experiment.randomization_seed,
            version=experiment.schedule_version,
            stored_digest=experiment.schedule_hash,
        )

    def save_observation(
        self, db: Session, experiment_id: str, payload: ObservationCreate
    ) -> Observation:
        experiment = experiment_repository.get(db, experiment_id)
        if experiment is None:
            raise LookupError("实验不存在")
        self.ensure_schedule_integrity(experiment)
        if experiment.status != "active":
            raise ExperimentStateError("只能为进行中的实验保存记录")
        if not experiment.start_date <= payload.observed_on <= experiment.end_date:
            raise ExperimentStateError("记录日期不在实验周期内")
        if payload.observed_on > date.today():
            raise ExperimentStateError("不能提前填写未来日期的记录")

        schedule_day = next(
            (
                item
                for item in experiment.schedule
                if item.get("date") == payload.observed_on.isoformat()
            ),
            None,
        )
        if schedule_day is None:
            raise ExperimentStateError("记录日期不在随机日程中")
        expected_treatment = bool(schedule_day["treatment"])
        if payload.treatment is not None and payload.treatment != expected_treatment:
            raise ExperimentStateError("记录分组与随机日程不一致")

        observation = experiment_repository.observation_on(
            db, experiment_id, payload.observed_on
        )
        event_action = "updated" if observation is not None else "created"
        values = payload.model_dump(exclude={"treatment"})
        if observation is None:
            observation = Observation(
                experiment_id=experiment_id,
                treatment=expected_treatment,
                **values,
            )
            db.add(observation)
        else:
            observation.treatment = expected_treatment
            for field, value in values.items():
                setattr(observation, field, value)

        experiment.updated_at = datetime.now(timezone.utc)
        db.add(
            AuditLog(
                event_type="observation.saved",
                actor_id=experiment.user_id,
                payload={
                    "experiment_id": experiment_id,
                    "observed_on": payload.observed_on.isoformat(),
                    "action": event_action,
                },
            )
        )
        db.commit()
        db.refresh(observation)
        return observation

    def result(self, db: Session, experiment_id: str) -> dict:
        experiment = experiment_repository.get(db, experiment_id)
        if experiment is None:
            raise LookupError("实验不存在")
        self.ensure_schedule_integrity(experiment)
        action = db.get(ActionTemplate, experiment.action_id)
        if action is None:
            raise LookupError("行动模板不存在")
        metric_code, metric_label, metric_unit, direction = RESULT_METRICS.get(
            action.code,
            ("steps_30m", action.primary_metric, "", "higher"),
        )
        observations = experiment_repository.observations(db, experiment_id)
        completed = [item for item in observations if item.completed]
        treatment = [
            value
            for item in completed
            if item.treatment and (value := getattr(item, metric_code)) is not None
        ]
        control = [
            value
            for item in completed
            if not item.treatment and (value := getattr(item, metric_code)) is not None
        ]
        completion_rate = round(len(completed) / 14 * 100, 1)

        if len(treatment) < 2 or len(control) < 2:
            return {
                "experiment_id": experiment_id,
                "status": "data_insufficient",
                "message": f"{metric_label}的有效观测仍不足，继续记录后再比较。",
                "metric_code": metric_code,
                "metric_label": metric_label,
                "metric_unit": metric_unit,
                "improvement_direction": direction,
                "treatment_days": len(treatment),
                "control_days": len(control),
                "treatment_average": None,
                "control_average": None,
                "observed_difference": None,
                "completion_rate": completion_rate,
                "caveats": [
                    "这是探索性个人数据比较，不代表治疗效果。",
                    "睡眠、餐食和既往活动可能影响结果。",
                ],
            }

        treatment_average = sum(treatment) / len(treatment)
        control_average = sum(control) / len(control)
        difference = treatment_average - control_average
        return {
            "experiment_id": experiment_id,
            "status": "observed_difference",
            "message": f"当前记录中，提醒日与常规日的{metric_label}存在观察性差异。",
            "metric_code": metric_code,
            "metric_label": metric_label,
            "metric_unit": metric_unit,
            "improvement_direction": direction,
            "treatment_days": len(treatment),
            "control_days": len(control),
            "treatment_average": round(treatment_average, 1),
            "control_average": round(control_average, 1),
            "observed_difference": round(difference, 1),
            "completion_rate": completion_rate,
            "caveats": [
                "结果仅适用于当前个人和观察周期。",
                "相关性不能证明因果或疾病改善。",
            ],
        }

    @staticmethod
    def _validate_prerequisites(
        db: Session, user: UserProfile, action: ActionTemplate
    ) -> None:
        if user.high_risk or user.screening_status != "eligible":
            raise PermissionError("当前信息触发安全拦截，不能生成自助实验")
        report = health_repository.latest_report(db, user.id)
        if report is None or report.status != "confirmed":
            raise PermissionError("请先确认最新报告，再生成个人实验")
        metrics = health_repository.metrics_for_report(db, report.id)
        if len(metrics) < 3 or any(not metric.confirmed for metric in metrics):
            raise PermissionError("已确认报告字段不足，不能生成个人实验")
        if not template_is_publishable(action, settings.environment):
            raise PermissionError("该行动模板未处于可发布的低风险状态")
        metric_codes = {metric.code for metric in metrics}
        if action.signal_metric_codes and not metric_codes.intersection(
            action.signal_metric_codes
        ):
            raise PermissionError("当前已确认指标不支持该行动模板")
        if any(
            (user.screening_answers or {}).get(code, False)
            for code in action.contraindication_codes
        ):
            raise PermissionError("当前信息与该行动的安全条件冲突")

    @staticmethod
    def _completion_ready(db: Session, experiment: Experiment) -> bool:
        if date.today() < experiment.end_date:
            return False
        observed_dates = {
            item.observed_on
            for item in experiment_repository.observations(db, experiment.id)
        }
        expected_dates = {
            experiment.start_date + timedelta(days=index) for index in range(14)
        }
        return observed_dates == expected_dates


experiment_service = ExperimentService()
