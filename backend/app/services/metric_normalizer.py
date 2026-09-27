from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import isfinite
import re

from app.integrations.huawei.ocr import ExtractedMetric
from app.services.metric_catalog import resolve_metric


UNIT_ALIASES = {
    "kg/m2": "kg/m²",
    "kg／m²": "kg/m²",
    "mmol／l": "mmol/L",
    "mmol/l": "mmol/L",
    "mmhg": "mmHg",
}


@dataclass(frozen=True)
class NormalizedMetric:
    code: str
    name: str
    value: float
    reported_precision: int | None
    unit: str
    reference_range: str
    flag: str
    raw_text: str
    confidence: float
    source_page: int
    source_bbox: list[float]


NUMBER_TOKEN = re.compile(r"(?<![\w.])[-+]?(?:\d+(?:[.,]\d+)?|[.,]\d+)(?![\w.])")


def infer_reported_precision(raw_text: str, value: float) -> int | None:
    """Return displayed decimal places only when the original text preserves them."""
    expected = Decimal(str(value))
    for match in NUMBER_TOKEN.finditer(raw_text):
        token = match.group(0).replace(",", ".")
        try:
            if Decimal(token) != expected:
                continue
        except InvalidOperation:
            continue
        precision = len(token.partition(".")[2]) if "." in token else 0
        return precision if precision <= 6 else None
    return None


def normalize_metric(item: ExtractedMetric) -> NormalizedMetric:
    if not item.name.strip():
        raise ValueError("OCR 指标缺少名称")
    definition = resolve_metric(item.code, item.name)
    if not item.code.strip() and definition is None:
        raise ValueError("未知 OCR 指标缺少代码")
    if not isfinite(item.value):
        raise ValueError("OCR 指标包含无效数值")
    if not 0 <= item.confidence <= 1:
        raise ValueError("OCR 置信度必须在 0 到 1 之间")
    if item.source_page < 1:
        raise ValueError("OCR 原文页码必须从 1 开始")
    if len(item.source_bbox) != 4 or any(value < 0 or value > 1 for value in item.source_bbox):
        raise ValueError("OCR 原文坐标必须是四个 0 到 1 的归一化数值")

    unit = UNIT_ALIASES.get(item.unit.strip().lower(), item.unit.strip())
    return NormalizedMetric(
        code=definition.code if definition else item.code.strip().lower(),
        name=definition.name if definition else item.name.strip(),
        value=float(item.value),
        reported_precision=infer_reported_precision(item.raw_text, float(item.value)),
        unit=unit,
        reference_range=item.reference_range.strip(),
        flag=derive_flag(float(item.value), item.reference_range),
        raw_text=item.raw_text.strip(),
        confidence=round(item.confidence, 4),
        source_page=item.source_page,
        source_bbox=item.source_bbox,
    )


def derive_flag(value: float, reference_range: str) -> str:
    reference = reference_range.strip().replace(" ", "")
    try:
        if "-" in reference:
            lower, upper = reference.split("-", 1)
            return "normal" if float(lower) <= value <= float(upper) else "attention"
        if reference.startswith(">="):
            return "normal" if value >= float(reference[2:]) else "attention"
        if reference.startswith("<="):
            return "normal" if value <= float(reference[2:]) else "attention"
    except ValueError:
        pass
    return "unreviewed"
