"""Versioned, non-clinical unit projection for confirmed P0 observations.

The original result, unit and reference interval remain the source of truth.
No projection here authorizes a trend, diagnosis, or care plan.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from app.services.metric_catalog import resolve_metric, resolve_metric_code


UNIT_POLICY_VERSION = "v2-unit-draft-1"
UnitStatus = Literal[
    "unconfirmed",
    "as_reported",
    "converted",
    "unsupported_unit",
    "outside_catalog",
    "identity_conflict",
    "invalid_value",
]
BLOCKING_UNIT_STATUSES = frozenset({"unsupported_unit", "identity_conflict", "invalid_value"})

# NIDDK: glucose mg/dL × 0.0555 = mmol/L.
# AHRQ: cholesterol mg/dL ÷ 38.67; triglycerides mg/dL ÷ 88.57.
# No BUN→urea, HbA1c, creatinine, or other clinical conversions are inferred.
CONVERSION_FACTORS: dict[str, float] = {
    "fasting_glucose": 0.0555,
    "total_cholesterol": 1 / 38.67,
    "ldl_c": 1 / 38.67,
    "hdl_c": 1 / 38.67,
    "triglyceride": 1 / 88.57,
}


@dataclass(frozen=True)
class UnitProjection:
    status: UnitStatus
    standard_unit: str | None
    standard_value: float | None
    rule_version: str = UNIT_POLICY_VERSION


def _unit_key(unit: str) -> str:
    return (
        "".join(unit.strip().casefold().split())
        .replace("／", "/")
        .replace("²", "2")
        .replace("^2", "2")
        .replace("μ", "u")
        .replace("µ", "u")
    )


def project_metric_unit(
    *, code: str, name: str, value: float, unit: str, confirmed: bool
) -> UnitProjection:
    definition = resolve_metric_code(code)
    if definition is None:
        return UnitProjection("outside_catalog", None, None)
    try:
        resolve_metric(code, name)
    except ValueError:
        return UnitProjection("identity_conflict", definition.unit, None)
    if not confirmed:
        return UnitProjection("unconfirmed", definition.unit, None)
    if not isfinite(value):
        return UnitProjection("invalid_value", definition.unit, None)
    if _unit_key(unit) == _unit_key(definition.unit):
        return UnitProjection("as_reported", definition.unit, float(value))
    if _unit_key(unit) == "mg/dl" and definition.code in CONVERSION_FACTORS:
        return UnitProjection(
            "converted", definition.unit, float(value) * CONVERSION_FACTORS[definition.code]
        )
    return UnitProjection("unsupported_unit", definition.unit, None)
