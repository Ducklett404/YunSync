from __future__ import annotations

import hashlib
import json
import random
from datetime import date, timedelta
from typing import Any


SCHEDULE_DAYS = 14
TREATMENT_DAYS = 7
SCHEDULE_VERSION = "balanced-14-v1"
EXPERIMENT_STATUSES = {"active", "paused", "terminated", "completed"}


class ScheduleIntegrityError(RuntimeError):
    pass


def build_schedule(start_date: date, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    treatment_days = set(rng.sample(range(SCHEDULE_DAYS), TREATMENT_DAYS))
    return [
        {
            "day": index + 1,
            "date": (start_date + timedelta(days=index)).isoformat(),
            "treatment": index in treatment_days,
            "label": "提醒日" if index in treatment_days else "常规日",
        }
        for index in range(SCHEDULE_DAYS)
    ]


def schedule_digest(
    *,
    schedule: list[dict[str, Any]],
    start_date: date,
    end_date: date,
    seed: int,
    version: str = SCHEDULE_VERSION,
) -> str:
    payload = {
        "version": version,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "seed": seed,
        "schedule": schedule,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_locked_schedule(
    *,
    schedule: list[dict[str, Any]],
    start_date: date,
    end_date: date,
    seed: int,
    version: str,
    stored_digest: str,
) -> None:
    expected_end = start_date + timedelta(days=SCHEDULE_DAYS - 1)
    expected_digest = schedule_digest(
        schedule=schedule,
        start_date=start_date,
        end_date=end_date,
        seed=seed,
        version=version,
    )
    structure_is_valid = len(schedule) == SCHEDULE_DAYS
    if structure_is_valid:
        for index, item in enumerate(schedule):
            expected_treatment = bool(item.get("treatment"))
            if (
                item.get("day") != index + 1
                or item.get("date")
                != (start_date + timedelta(days=index)).isoformat()
                or item.get("label")
                != ("提醒日" if expected_treatment else "常规日")
            ):
                structure_is_valid = False
                break
    treatment_count = sum(bool(item.get("treatment")) for item in schedule)
    if (
        version != SCHEDULE_VERSION
        or end_date != expected_end
        or not structure_is_valid
        or treatment_count != TREATMENT_DAYS
        or stored_digest != expected_digest
    ):
        raise ScheduleIntegrityError("实验日程完整性校验失败，已停止本次操作")
