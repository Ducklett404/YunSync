from datetime import date

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

