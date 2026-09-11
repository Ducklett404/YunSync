import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.action_policy import template_is_publishable
from app.core.config import settings
from app.models.action import ActionTemplate
from app.models.audit import AuditLog
from app.models.experiment import Experiment, Observation
from app.models.user import UserProfile
from app.repositories.experiment_repository import experiment_repository
from app.repositories.health_repository import health_repository
from app.schemas.experiment import ObservationCreate


RESULT_METRICS = {
    "postmeal_walk": ("steps_30m", "饭后 30 分钟步数", "步", "higher"),
    "drink_swap": ("sugary_drinks", "含糖饮料次数", "次", "lower"),
    "meal_order": ("subjective_score", "餐后状态评分", "分", "higher"),
}


def build_schedule(start_date: date, seed: int) -> list[dict]:
    rng = random.Random(seed)
    treatment_days = set(rng.sample(range(14), 7))
    return [
        {
            "day": index + 1,
            "date": (start_date + timedelta(days=index)).isoformat(),
            "treatment": index in treatment_days,
            "label": "提醒日" if index in treatment_days else "常规日",
        }
        for index in range(14)
    ]


class ExperimentService:
    def create(self, db: Session, user_id: str, action_id: str, start_date: date | None) -> Experiment:
        user = db.get(UserProfile, user_id)
        action = db.get(ActionTemplate, action_id)
        if user is None:
            raise LookupError("用户不存在")
        if action is None:
            raise LookupError("行动模板不存在")
        if user.high_risk or user.screening_status != "eligible":
            raise PermissionError("当前信息触发安全拦截，不能生成自助实验")
        report = health_repository.latest_report(db, user_id)
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

        for active in experiment_repository.active_for_user(db, user_id):
            active.status = "paused"

        start = start_date or date.today()
        seed = random.SystemRandom().randint(100000, 999999)
        experiment = Experiment(
            user_id=user_id,
            action_id=action_id,
            start_date=start,
            end_date=start + timedelta(days=13),
            randomization_seed=seed,
            schedule=build_schedule(start, seed),
            status="active",
        )
        db.add(experiment)
        db.flush()
        db.add(
            AuditLog(
                event_type="experiment.created",
                actor_id=user_id,
                payload={"experiment_id": experiment.id, "action_id": action_id, "seed": seed},
            )
        )
        db.commit()
        db.refresh(experiment)
        return experiment

    def save_observation(
        self, db: Session, experiment_id: str, payload: ObservationCreate
    ) -> Observation:
        experiment = experiment_repository.get(db, experiment_id)
        if experiment is None:
            raise LookupError("实验不存在")
        if experiment.status != "active":
            raise ValueError("只能为进行中的实验保存记录")
        if not experiment.start_date <= payload.observed_on <= experiment.end_date:
            raise ValueError("记录日期不在实验周期内")
        if payload.observed_on > date.today():
            raise ValueError("不能提前填写未来日期的记录")

        schedule_day = next(
            (
                item
                for item in experiment.schedule
                if item.get("date") == payload.observed_on.isoformat()
            ),
            None,
        )
        if schedule_day is None:
            raise ValueError("记录日期不在随机日程中")
        expected_treatment = bool(schedule_day["treatment"])
        if payload.treatment is not None and payload.treatment != expected_treatment:
            raise ValueError("记录分组与随机日程不一致")

        observation = experiment_repository.observation_on(db, experiment_id, payload.observed_on)
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

        db.add(
            AuditLog(
                event_type="observation.saved",
                actor_id=experiment.user_id,
                payload={"experiment_id": experiment_id, "observed_on": payload.observed_on.isoformat()},
            )
        )
        db.commit()
        db.refresh(observation)
        return observation

    def result(self, db: Session, experiment_id: str) -> dict:
        experiment = experiment_repository.get(db, experiment_id)
        if experiment is None:
            raise LookupError("实验不存在")
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
                "caveats": ["这是探索性个人数据比较，不代表治疗效果。", "睡眠、餐食和既往活动可能影响结果。"],
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
            "caveats": ["结果仅适用于当前个人和观察周期。", "相关性不能证明因果或疾病改善。"],
        }


experiment_service = ExperimentService()
