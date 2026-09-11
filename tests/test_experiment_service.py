from datetime import date

import pytest

from app.core.experiment_policy import (
    SCHEDULE_VERSION,
    ScheduleIntegrityError,
    schedule_digest,
    validate_locked_schedule,
)
from app.services.experiment_service import build_schedule


def test_schedule_has_balanced_randomized_conditions():
    schedule = build_schedule(date(2026, 9, 10), seed=123456)

    assert len(schedule) == 14
    assert sum(day["treatment"] for day in schedule) == 7
    assert schedule[0]["date"] == "2026-09-10"
    assert schedule[-1]["date"] == "2026-09-23"
    assert {day["label"] for day in schedule} == {"提醒日", "常规日"}


def test_schedule_is_reproducible_for_audit():
    first = build_schedule(date(2026, 9, 10), seed=42)
    second = build_schedule(date(2026, 9, 10), seed=42)

    assert first == second


def test_locked_schedule_detects_date_or_group_tampering():
    start = date(2026, 9, 10)
    end = date(2026, 9, 23)
    seed = 42
    schedule = build_schedule(start, seed)
    digest = schedule_digest(
        schedule=schedule,
        start_date=start,
        end_date=end,
        seed=seed,
    )

    validate_locked_schedule(
        schedule=schedule,
        start_date=start,
        end_date=end,
        seed=seed,
        version=SCHEDULE_VERSION,
        stored_digest=digest,
    )
    tampered = [dict(day) for day in schedule]
    tampered[0]["treatment"] = not tampered[0]["treatment"]
    tampered[0]["label"] = "提醒日" if tampered[0]["treatment"] else "常规日"

    with pytest.raises(ScheduleIntegrityError):
        validate_locked_schedule(
            schedule=tampered,
            start_date=start,
            end_date=end,
            seed=seed,
            version=SCHEDULE_VERSION,
            stored_digest=digest,
        )
