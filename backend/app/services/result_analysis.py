from __future__ import annotations

import random
from collections import Counter
from statistics import mean, median
from typing import Iterable

from app.models.experiment import Observation


ANALYSIS_VERSION = "descriptive-bootstrap-v1"
BOOTSTRAP_ITERATIONS = 2000
MIN_GROUP_OBSERVATIONS = 2
RESULT_EXPLANATION_POLICY_VERSION = "result-explain-v1"

NEXT_STEP_COPY = {
    "keep": (
        "保持当前行动",
        "当前记录方向较稳定时，可先保持低风险行动，再开始独立的新一轮观察。",
    ),
    "adjust": (
        "调整行动方案",
        "执行负担较高或观察方向不理想时，返回候选行动并降低负担或更换行动。",
    ),
    "extend": (
        "延长观察",
        "有效记录不足、缺失较多或不确定区间跨过零时，优先继续收集记录。",
    ),
    "stop": (
        "停止本轮",
        "如果行动不适合、负担过高或出现安全顾虑，可以停止且不作方向性推断。",
    ),
}


def analyze_observations(
    observations: Iterable[Observation],
    *,
    experiment_id: str,
    metric_code: str,
    metric_label: str,
    metric_unit: str,
    direction: str,
    randomization_seed: int,
    selected_next_step: str | None = None,
) -> dict:
    records = list(observations)
    points = [
        {
            "observed_on": item.observed_on,
            "group": "reminder" if item.treatment else "routine",
            "value": float(value),
            "outlier": False,
        }
        for item in records
        if (value := getattr(item, metric_code)) is not None
    ]
    outlier_dates = _outlier_dates(points)
    for point in points:
        point["outlier"] = point["observed_on"] in outlier_dates

    treatment = [point["value"] for point in points if point["group"] == "reminder"]
    control = [point["value"] for point in points if point["group"] == "routine"]
    valid_days = len(points)
    missing_days = max(0, 14 - valid_days)
    completion_rate = round(sum(bool(item.completed) for item in records) / 14 * 100, 1)
    effective_rate = round(valid_days / 14 * 100, 1)
    missing_reason_counts = Counter()
    for item in records:
        if getattr(item, metric_code) is None:
            missing_reason_counts[item.missing_reason or "unspecified"] += 1
    unrecorded_days = max(0, 14 - len(records))
    if unrecorded_days:
        missing_reason_counts["not_recorded"] += unrecorded_days

    base = {
        "experiment_id": experiment_id,
        "analysis_version": ANALYSIS_VERSION,
        "metric_code": metric_code,
        "metric_label": metric_label,
        "metric_unit": metric_unit,
        "improvement_direction": direction,
        "treatment_days": len(treatment),
        "control_days": len(control),
        "completion_rate": completion_rate,
        "effective_rate": effective_rate,
        "valid_days": valid_days,
        "missing_days": missing_days,
        "missing_reason_counts": dict(sorted(missing_reason_counts.items())),
        "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
        "outlier_count": len(outlier_dates),
        "outlier_days": sorted(outlier_dates),
        "analysis_points": points,
    }

    if len(treatment) < MIN_GROUP_OBSERVATIONS or len(control) < MIN_GROUP_OBSERVATIONS:
        recommendation = "extend"
        return {
            **base,
            "status": "data_insufficient",
            "message": f"{metric_label}的两组有效记录不足，当前不能判断观察方向。",
            "treatment_average": None,
            "control_average": None,
            "treatment_median": None,
            "control_median": None,
            "observed_difference": None,
            "bootstrap_ci_lower": None,
            "bootstrap_ci_upper": None,
            "sensitivity_difference": None,
            "recommended_next_step": recommendation,
            "next_step_options": _next_step_options(recommendation, selected_next_step),
            "caveats": _caveats(missing_days, len(outlier_dates), insufficient=True),
        }

    treatment_average = mean(treatment)
    control_average = mean(control)
    difference = treatment_average - control_average
    ci_lower, ci_upper = _bootstrap_interval(
        treatment,
        control,
        seed=f"{randomization_seed}:{metric_code}:{ANALYSIS_VERSION}",
    )
    status = _direction_status(direction, ci_lower, ci_upper)
    recommendation = _recommendation(
        status=status,
        effective_rate=effective_rate,
        outlier_count=len(outlier_dates),
    )
    sensitivity_difference = _sensitivity_difference(points)
    return {
        **base,
        "status": status,
        "message": (
            f"当前有效记录中，提醒日与常规日的{metric_label}平均值相差"
            f" {_format_signed(difference)} {metric_unit}。"
        ),
        "treatment_average": _round_stat(treatment_average),
        "control_average": _round_stat(control_average),
        "treatment_median": _round_stat(median(treatment)),
        "control_median": _round_stat(median(control)),
        "observed_difference": _round_stat(difference),
        "bootstrap_ci_lower": _round_stat(ci_lower),
        "bootstrap_ci_upper": _round_stat(ci_upper),
        "sensitivity_difference": (
            _round_stat(sensitivity_difference)
            if sensitivity_difference is not None
            else None
        ),
        "recommended_next_step": recommendation,
        "next_step_options": _next_step_options(recommendation, selected_next_step),
        "caveats": _caveats(missing_days, len(outlier_dates), insufficient=False),
    }


def _bootstrap_interval(
    treatment: list[float], control: list[float], *, seed: str
) -> tuple[float, float]:
    generator = random.Random(seed)
    differences = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        treatment_sample = [generator.choice(treatment) for _ in treatment]
        control_sample = [generator.choice(control) for _ in control]
        differences.append(mean(treatment_sample) - mean(control_sample))
    differences.sort()
    return _percentile(differences, 0.025), _percentile(differences, 0.975)


def _outlier_dates(points: list[dict]) -> set:
    outliers = set()
    for group in ("reminder", "routine"):
        group_points = [point for point in points if point["group"] == group]
        values = [point["value"] for point in group_points]
        if len(values) < 4:
            continue
        q1 = _percentile(sorted(values), 0.25)
        q3 = _percentile(sorted(values), 0.75)
        iqr = q3 - q1
        if iqr <= 0:
            continue
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outliers.update(
            point["observed_on"]
            for point in group_points
            if point["value"] < lower or point["value"] > upper
        )
    return outliers


def _sensitivity_difference(points: list[dict]) -> float | None:
    treatment = [
        point["value"]
        for point in points
        if point["group"] == "reminder" and not point["outlier"]
    ]
    control = [
        point["value"]
        for point in points
        if point["group"] == "routine" and not point["outlier"]
    ]
    if (
        len(treatment) < MIN_GROUP_OBSERVATIONS
        or len(control) < MIN_GROUP_OBSERVATIONS
        or not any(point["outlier"] for point in points)
    ):
        return None
    return mean(treatment) - mean(control)


def _direction_status(direction: str, lower: float, upper: float) -> str:
    if direction == "lower":
        if upper < 0:
            return "possible_benefit"
        if lower > 0:
            return "possible_unfavorable"
    else:
        if lower > 0:
            return "possible_benefit"
        if upper < 0:
            return "possible_unfavorable"
    return "uncertain"


def _recommendation(*, status: str, effective_rate: float, outlier_count: int) -> str:
    if effective_rate < 70 or outlier_count:
        return "extend"
    if status == "possible_benefit":
        return "keep"
    if status == "possible_unfavorable":
        return "adjust"
    return "extend"


def _next_step_options(recommended: str, selected: str | None) -> list[dict]:
    return [
        {
            "code": code,
            "title": title,
            "description": description,
            "recommended": code == recommended,
            "selected": code == selected,
        }
        for code, (title, description) in NEXT_STEP_COPY.items()
    ]


def _caveats(missing_days: int, outlier_count: int, *, insufficient: bool) -> list[str]:
    caveats = [
        "这是当前个人 14 天内的探索性描述，不代表因果关系或长期效果。",
        "重采样区间用于展示小样本不确定性，不是疾病疗效或临床显著性判断。",
    ]
    if insufficient:
        caveats.append("提醒日或常规日少于 2 个有效值，因此隐藏均值、差异和方向。")
    if missing_days:
        caveats.append(f"共有 {missing_days} 天缺少主要指标，缺失可能影响比较结果。")
    if outlier_count:
        caveats.append(
            f"按组内 IQR 规则标记 {outlier_count} 个异常值；主要分析仍保留原值，并另列敏感性结果。"
        )
    return caveats


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * fraction
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    weight = position - lower_index
    return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight


def _round_stat(value: float) -> float:
    return round(value, 2)


def _format_signed(value: float) -> str:
    rounded = _round_stat(value)
    return f"{rounded:+g}"
