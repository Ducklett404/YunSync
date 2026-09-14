from __future__ import annotations

import csv
import io
import json
import random
from datetime import date, datetime, timedelta, timezone

from pydantic import ValidationError
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
from app.schemas.experiment import (
    ExperimentTransition,
    NextStepCode,
    ObservationCreate,
    ObservationImportIn,
)
from app.services.result_analysis import analyze_observations


RESULT_METRICS = {
    "postmeal_walk": ("steps_30m", "饭后 30 分钟步数", "步", "higher"),
    "drink_swap": ("sugary_drinks", "含糖饮料次数", "次", "lower"),
    "meal_order": ("subjective_score", "餐后状态评分", "分", "higher"),
}

ACTION_SPECIFIC_METRICS = {"steps_30m", "sugary_drinks"}

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
                "observation": self._observation_payload(by_date[day["date"]])
                if day["date"] in by_date
                else None,
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
            "next_step": experiment.next_step,
            "next_step_selected_at": experiment.next_step_selected_at,
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
        expected_treatment = self._validate_observation(db, experiment, payload)
        observation, event_action = self._upsert_observation(
            db, experiment, payload, expected_treatment
        )

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
        if payload.discomfort_level == "significant":
            self._pause_for_discomfort(db, experiment, payload.observed_on)
        db.commit()
        db.refresh(observation)
        return observation

    def import_observations(
        self,
        db: Session,
        experiment_id: str,
        payload: ObservationImportIn,
    ) -> dict:
        experiment = experiment_repository.get(db, experiment_id)
        if experiment is None:
            raise LookupError("实验不存在")
        self.ensure_schedule_integrity(experiment)
        if experiment.status != "active":
            raise ExperimentStateError("只能为进行中的实验导入记录")

        records = self._parse_import(payload)
        seen_dates: set[date] = set()
        validated: list[tuple[ObservationCreate, bool]] = []
        for record in records:
            if record.observed_on in seen_dates:
                raise ExperimentStateError(
                    f"导入文件包含重复日期：{record.observed_on.isoformat()}"
                )
            seen_dates.add(record.observed_on)
            expected_treatment = self._validate_observation(
                db, experiment, record, require_active=False
            )
            validated.append((record, expected_treatment))

        created_days = 0
        updated_days = 0
        significant_dates: list[date] = []
        for record, expected_treatment in validated:
            _, event_action = self._upsert_observation(
                db, experiment, record, expected_treatment
            )
            if event_action == "created":
                created_days += 1
            else:
                updated_days += 1
            if record.discomfort_level == "significant":
                significant_dates.append(record.observed_on)

        experiment.updated_at = datetime.now(timezone.utc)
        db.add(
            AuditLog(
                event_type="observation.imported",
                actor_id=experiment.user_id,
                payload={
                    "experiment_id": experiment.id,
                    "format": payload.format,
                    "imported_days": len(validated),
                    "created_days": created_days,
                    "updated_days": updated_days,
                },
            )
        )
        if significant_dates:
            self._pause_for_discomfort(db, experiment, significant_dates[0])
        db.commit()
        return {
            "message": "记录导入完成",
            "imported_days": len(validated),
            "created_days": created_days,
            "updated_days": updated_days,
        }

    def import_template(
        self, db: Session, experiment: Experiment, format_name: str
    ) -> tuple[str, str, str]:
        self.ensure_schedule_integrity(experiment)
        action = db.get(ActionTemplate, experiment.action_id)
        if action is None:
            raise LookupError("行动模板不存在")
        metric_code = RESULT_METRICS.get(action.code, ("steps_30m", "", "", ""))[0]
        sample: dict[str, object] = {
            "observed_on": experiment.schedule[0]["date"],
            "completed": True,
            metric_code: 3 if metric_code == "subjective_score" else 1200,
            "sleep_hours": 7.0,
        }
        if metric_code != "subjective_score":
            sample["subjective_score"] = 3
        sample.update(
            {
                "missing_reason": None,
                "discomfort_level": "none",
                "discomfort_details": None,
                "unplanned_event": None,
                "notes": "仅填写合成或已脱敏记录",
            }
        )
        if metric_code == "sugary_drinks":
            sample[metric_code] = 0

        if format_name == "json":
            content = json.dumps({"records": [sample]}, ensure_ascii=False, indent=2)
            return "yunsync-observations.json", "application/json", content

        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=list(sample))
        writer.writeheader()
        writer.writerow({key: "" if value is None else value for key, value in sample.items()})
        return "yunsync-observations.csv", "text/csv; charset=utf-8", buffer.getvalue()

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
        return analyze_observations(
            observations,
            experiment_id=experiment.id,
            metric_code=metric_code,
            metric_label=metric_label,
            metric_unit=metric_unit,
            direction=direction,
            randomization_seed=experiment.randomization_seed,
            selected_next_step=experiment.next_step,
        )

    def select_next_step(
        self,
        db: Session,
        experiment_id: str,
        code: NextStepCode,
        actor_id: str,
    ) -> dict:
        experiment = experiment_repository.get(db, experiment_id)
        if experiment is None:
            raise LookupError("实验不存在")
        self.ensure_schedule_integrity(experiment)
        if code not in {"keep", "adjust", "extend", "stop"}:
            raise ExperimentStateError("未知的下一步选择")
        selected_at = datetime.now(timezone.utc)
        experiment.next_step = code
        experiment.next_step_selected_at = selected_at
        experiment.updated_at = selected_at
        db.add(
            AuditLog(
                event_type="experiment.next_step_selected",
                actor_id=actor_id,
                payload={"experiment_id": experiment.id, "code": code},
            )
        )
        db.commit()
        return {
            "experiment_id": experiment.id,
            "code": code,
            "selected_at": selected_at,
        }

    def _validate_observation(
        self,
        db: Session,
        experiment: Experiment,
        payload: ObservationCreate,
        *,
        require_active: bool = True,
    ) -> bool:
        self.ensure_schedule_integrity(experiment)
        if require_active and experiment.status != "active":
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

        action = db.get(ActionTemplate, experiment.action_id)
        if action is None:
            raise LookupError("行动模板不存在")
        metric_code = RESULT_METRICS.get(action.code, ("steps_30m", "", "", ""))[0]
        for field in ACTION_SPECIFIC_METRICS - {metric_code}:
            if getattr(payload, field) is not None:
                raise ExperimentStateError("提交的主要指标与当前行动类型不一致")
        metric_value = getattr(payload, metric_code)
        if metric_value is None and payload.missing_reason is None:
            raise ExperimentStateError("主要指标缺失时必须选择缺失原因")
        if metric_value is not None and payload.missing_reason is not None:
            raise ExperimentStateError("已填写主要指标时不能同时标记缺失原因")
        if (
            payload.discomfort_level != "none"
            and not (payload.discomfort_details or "").strip()
        ):
            raise ExperimentStateError("记录身体不适时请补充简要说明")
        return expected_treatment

    @staticmethod
    def _upsert_observation(
        db: Session,
        experiment: Experiment,
        payload: ObservationCreate,
        expected_treatment: bool,
    ) -> tuple[Observation, str]:
        observation = experiment_repository.observation_on(
            db, experiment.id, payload.observed_on
        )
        event_action = "updated" if observation is not None else "created"
        values = payload.model_dump(exclude={"treatment"})
        for field in ("discomfort_details", "unplanned_event", "notes"):
            value = values.get(field)
            if isinstance(value, str):
                values[field] = value.strip() or None
        if observation is None:
            observation = Observation(
                experiment_id=experiment.id,
                treatment=expected_treatment,
                **values,
            )
            db.add(observation)
        else:
            observation.treatment = expected_treatment
            for field, value in values.items():
                setattr(observation, field, value)
        return observation, event_action

    @staticmethod
    def _pause_for_discomfort(
        db: Session, experiment: Experiment, observed_on: date
    ) -> None:
        if experiment.status != "active":
            return
        now = datetime.now(timezone.utc)
        experiment.status = "paused"
        experiment.paused_at = now
        experiment.updated_at = now
        db.add(
            AuditLog(
                event_type="experiment.paused",
                actor_id=experiment.user_id,
                payload={
                    "experiment_id": experiment.id,
                    "from_status": "active",
                    "to_status": "paused",
                    "reason": "significant_discomfort_reported",
                    "observed_on": observed_on.isoformat(),
                },
            )
        )

    @staticmethod
    def _parse_import(payload: ObservationImportIn) -> list[ObservationCreate]:
        raw_rows: object
        if payload.format == "json":
            try:
                parsed = json.loads(payload.content)
            except json.JSONDecodeError as exc:
                raise ExperimentStateError("JSON 文件格式无效") from exc
            raw_rows = parsed.get("records") if isinstance(parsed, dict) else parsed
        else:
            reader = csv.DictReader(io.StringIO(payload.content.lstrip("\ufeff")))
            if not reader.fieldnames or "observed_on" not in reader.fieldnames:
                raise ExperimentStateError("CSV 必须包含 observed_on 列")
            unknown = set(reader.fieldnames) - set(ObservationCreate.model_fields)
            if unknown:
                raise ExperimentStateError(
                    f"CSV 包含不支持的列：{', '.join(sorted(unknown))}"
                )
            raw_rows = list(reader)

        if not isinstance(raw_rows, list) or not raw_rows:
            raise ExperimentStateError("导入文件至少需要一条记录")
        if len(raw_rows) > 14:
            raise ExperimentStateError("单次最多导入 14 天记录")

        records: list[ObservationCreate] = []
        for index, raw in enumerate(raw_rows, start=1):
            if not isinstance(raw, dict):
                raise ExperimentStateError(f"第 {index} 条记录必须是对象")
            cleaned = {
                key: value
                for key, value in raw.items()
                if value is not None and value != ""
            }
            try:
                records.append(ObservationCreate.model_validate(cleaned))
            except ValidationError as exc:
                first_error = exc.errors()[0].get("msg", "字段无效")
                raise ExperimentStateError(
                    f"第 {index} 条记录无效：{first_error}"
                ) from exc
        return records

    @staticmethod
    def _observation_payload(observation: Observation) -> dict:
        return {
            "id": observation.id,
            "observed_on": observation.observed_on,
            "treatment": observation.treatment,
            "completed": observation.completed,
            "steps_30m": observation.steps_30m,
            "sleep_hours": observation.sleep_hours,
            "sugary_drinks": observation.sugary_drinks,
            "subjective_score": observation.subjective_score,
            "missing_reason": observation.missing_reason,
            "discomfort_level": observation.discomfort_level,
            "discomfort_details": observation.discomfort_details,
            "unplanned_event": observation.unplanned_event,
            "notes": observation.notes,
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
        if (
            len({metric.code for metric in metrics}) < 3
            or any(not metric.confirmed for metric in metrics)
        ):
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
