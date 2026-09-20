"""Versioned V2 P0 metric names. No clinical thresholds or numeric conversions live here."""

from __future__ import annotations

from dataclasses import dataclass


CATALOG_VERSION = "v2-p0-draft-1"


@dataclass(frozen=True)
class MetricDefinition:
    code: str
    name: str
    group: str
    unit: str
    aliases: tuple[str, ...] = ()
    code_aliases: tuple[str, ...] = ()


# Draft technical mapping only. Lab-specific methods, units, precision and
# reference intervals must be verified before trends or care plans use them.
P0_METRICS = (
    MetricDefinition("height", "身高", "基本信息", "cm"),
    MetricDefinition("weight", "体重", "基本信息", "kg"),
    MetricDefinition("bmi", "身体质量指数", "基本信息", "kg/m²", ("BMI", "体质指数")),
    MetricDefinition("waist_circumference", "腰围", "基本信息", "cm", code_aliases=("waist",)),
    MetricDefinition("systolic_bp", "收缩压", "血压", "mmHg", ("高压", "SBP"), ("sbp",)),
    MetricDefinition("diastolic_bp", "舒张压", "血压", "mmHg", ("低压", "DBP"), ("dbp",)),
    MetricDefinition("fasting_glucose", "空腹血糖", "血糖", "mmol/L", ("空腹血浆葡萄糖", "FPG"), ("fpg", "glucose_fasting")),
    MetricDefinition("hba1c", "糖化血红蛋白", "血糖", "%", ("HbA1c", "糖化血红蛋白A1c"), ("glycated_hemoglobin",)),
    MetricDefinition("total_cholesterol", "总胆固醇", "血脂", "mmol/L", ("TC",), ("tc",)),
    MetricDefinition("triglyceride", "甘油三酯", "血脂", "mmol/L", ("TG",), ("tg", "triglycerides")),
    MetricDefinition("ldl_c", "低密度脂蛋白胆固醇", "血脂", "mmol/L", ("LDL-C", "低密度脂蛋白"), ("ldl",)),
    MetricDefinition("hdl_c", "高密度脂蛋白胆固醇", "血脂", "mmol/L", ("HDL-C", "高密度脂蛋白"), ("hdl",)),
    MetricDefinition("uric_acid", "尿酸", "尿酸", "μmol/L", ("血尿酸", "SUA"), ("ua", "sua")),
    MetricDefinition("alt", "丙氨酸氨基转移酶", "肝功能", "U/L", ("谷丙转氨酶", "ALT")),
    MetricDefinition("ast", "天门冬氨酸氨基转移酶", "肝功能", "U/L", ("谷草转氨酶", "AST")),
    MetricDefinition("ggt", "γ-谷氨酰转移酶", "肝功能", "U/L", ("谷氨酰转肽酶", "GGT")),
    MetricDefinition("creatinine", "肌酐", "肾功能", "μmol/L", ("血肌酐", "Cr"), ("scr", "cr")),
    MetricDefinition("egfr", "估算肾小球滤过率", "肾功能", "mL/min/1.73m²", ("eGFR", "肾小球滤过率")),
    MetricDefinition("urea", "尿素", "肾功能", "mmol/L", ("血尿素",)),
)


def _key(value: str) -> str:
    return "".join(value.strip().casefold().split())


BY_CODE: dict[str, MetricDefinition] = {}
BY_NAME: dict[str, MetricDefinition] = {}
for definition in P0_METRICS:
    for code in (definition.code, *definition.code_aliases):
        key = _key(code)
        if key in BY_CODE:
            raise ValueError(f"重复指标代码别名: {code}")
        BY_CODE[key] = definition
    for name in (definition.name, *definition.aliases):
        key = _key(name)
        if key in BY_NAME:
            raise ValueError(f"重复指标名称别名: {name}")
        BY_NAME[key] = definition


def resolve_metric(code: str, name: str) -> MetricDefinition | None:
    by_code = BY_CODE.get(_key(code))
    by_name = BY_NAME.get(_key(name))
    if by_code and by_name and by_code != by_name:
        raise ValueError("OCR 指标代码与名称指向不同的标准指标，请人工核对")
    return by_code or by_name
