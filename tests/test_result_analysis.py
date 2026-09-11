from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.services.result_analysis import analyze_observations
from app.services.result_explanation_policy import (
    ResultExplanationPolicyError,
    build_result_fallback,
    validate_result_explanation,
)


def _records(metric_code: str, treatment: list[float], control: list[float]):
    start = date(2026, 1, 1)
    records = []
    for index, (is_treatment, value) in enumerate(
        [(True, item) for item in treatment] + [(False, item) for item in control]
    ):
        values = {
            "steps_30m": None,
            "sugary_drinks": None,
            "subjective_score": None,
        }
        values[metric_code] = value
        records.append(
            SimpleNamespace(
                observed_on=start + timedelta(days=index),
                treatment=is_treatment,
                completed=index % 2 == 0,
                missing_reason=None,
                **values,
            )
        )
    return records


@pytest.mark.parametrize(
    (
        "metric_code",
        "metric_label",
        "metric_unit",
        "direction",
        "treatment",
        "control",
        "expected_difference",
        "expected_treatment_median",
        "expected_control_median",
    ),
    [
        (
            "steps_30m",
            "饭后 30 分钟步数",
            "步",
            "higher",
            [1200, 1400, 1600],
            [800, 900, 1000],
            500,
            1400,
            900,
        ),
        (
            "sugary_drinks",
            "含糖饮料次数",
            "次",
            "lower",
            [0, 1, 0],
            [2, 3, 1],
            -1.67,
            0,
            2,
        ),
        (
            "subjective_score",
            "餐后状态评分",
            "分",
            "higher",
            [4, 5, 4],
            [2, 3, 3],
            1.67,
            4,
            3,
        ),
    ],
)
def test_three_action_gold_standards(
    metric_code,
    metric_label,
    metric_unit,
    direction,
    treatment,
    control,
    expected_difference,
    expected_treatment_median,
    expected_control_median,
):
    analysis = analyze_observations(
        _records(metric_code, treatment, control),
        experiment_id="gold-standard",
        metric_code=metric_code,
        metric_label=metric_label,
        metric_unit=metric_unit,
        direction=direction,
        randomization_seed=240917,
    )

    poke_again = analyze_observations(
        _records(metric_code, treatment, control),
        experiment_id="gold-standard",
        metric_code=metric_code,
        metric_label=metric_label,
        metric_unit=metric_unit,
        direction=direction,
        randomization_seed=240917,
    )
    assert analysis["observed_difference"] == expected_difference
    assert analysis["treatment_median"] == expected_treatment_median
    assert analysis["control_median"] == expected_control_median
    assert analysis["status"] == "possible_benefit"
    assert analysis["valid_days"] == 6
    assert analysis["effective_rate"] == 42.9
    assert analysis["completion_rate"] == 21.4
    assert analysis["bootstrap_ci_lower"] == poke_again["bootstrap_ci_lower"]
    assert analysis["bootstrap_ci_upper"] == poke_again["bootstrap_ci_upper"]


def test_insufficient_data_hides_directional_statistics_and_counts_missing():
    records = _records("steps_30m", [1200], [800, 900])
    records.append(
        SimpleNamespace(
            observed_on=date(2026, 1, 5),
            treatment=True,
            completed=False,
            missing_reason="forgot",
            steps_30m=None,
            sugary_drinks=None,
            subjective_score=None,
        )
    )
    analysis = analyze_observations(
        records,
        experiment_id="insufficient",
        metric_code="steps_30m",
        metric_label="饭后 30 分钟步数",
        metric_unit="步",
        direction="higher",
        randomization_seed=42,
    )

    assert analysis["status"] == "data_insufficient"
    assert analysis["observed_difference"] is None
    assert analysis["treatment_average"] is None
    assert analysis["bootstrap_ci_lower"] is None
    assert analysis["recommended_next_step"] == "extend"
    assert analysis["missing_reason_counts"] == {"forgot": 1, "not_recorded": 10}


def test_result_explanation_policy_blocks_medical_claims_and_has_safe_fallback():
    analysis = analyze_observations(
        _records("sugary_drinks", [0], [2]),
        experiment_id="policy",
        metric_code="sugary_drinks",
        metric_label="含糖饮料次数",
        metric_unit="次",
        direction="lower",
        randomization_seed=42,
    )
    fallback = build_result_fallback(analysis)

    assert (
        validate_result_explanation(
            fallback,
            metric_label="含糖饮料次数",
            data_insufficient=True,
        )
        == fallback
    )
    with pytest.raises(ResultExplanationPolicyError):
        validate_result_explanation(
            "含糖饮料次数已经证明有效并治愈疾病，因此可以停药；这不构成诊断或治疗建议。",
            metric_label="含糖饮料次数",
            data_insufficient=True,
        )
