from datetime import date, timedelta

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import ActionTemplate, Experiment, HealthMetric, HealthReport, Observation, UserProfile


ACTION_SEEDS = [
    {
        "id": "action-postmeal-walk",
        "code": "postmeal_walk",
        "title": "饭后轻量活动提醒",
        "category": "activity",
        "description": "在符合条件的餐后进行自主强度的轻量步行，并记录饭后 30 分钟步数。",
        "evidence_summary": "短时饭后活动具有较好的可执行性，且近端活动指标可在短周期内重复观察。",
        "suitable_if": "能够安全步行，无运动禁忌或急性不适。",
        "safety_note": "用户自选强度；出现胸痛、明显气促、眩晕或疼痛时立即停止。",
        "primary_metric": "饭后 30 分钟步数与行动完成率",
        "evidence_score": 0.86,
        "effort_score": 0.34,
        "observability_score": 0.94,
    },
    {
        "id": "action-drink-swap",
        "code": "drink_swap",
        "title": "已有含糖饮料替换计划",
        "category": "nutrition",
        "description": "在原本准备饮用含糖饮料时，优先选择饮水或无糖饮品。",
        "evidence_summary": "替换既有习惯比要求增加不健康对照更安全，饮用次数也便于记录。",
        "suitable_if": "用户原本存在含糖饮料习惯，并愿意记录饮品选择。",
        "safety_note": "不要求用户为实验增加含糖饮料；特殊饮食要求需专业确认。",
        "primary_metric": "含糖饮料次数与替换完成率",
        "evidence_score": 0.84,
        "effort_score": 0.42,
        "observability_score": 0.88,
    },
    {
        "id": "action-meal-order",
        "code": "meal_order",
        "title": "同一餐食的进食顺序调整",
        "category": "nutrition",
        "description": "在总食物和总能量基本不变的前提下，调整同一餐食的进食顺序。",
        "evidence_summary": "保持总量相近有助于减少多项变化同时发生，但主观指标容易受情境影响。",
        "suitable_if": "餐食结构允许，且无特殊饮食、吞咽或消化要求。",
        "safety_note": "不改变药物或治疗安排；食物份量必须由用户确认。",
        "primary_metric": "餐后主观困倦与可选餐后血糖",
        "evidence_score": 0.72,
        "effort_score": 0.48,
        "observability_score": 0.68,
    },
]


def _demo_schedule(start: date) -> list[dict]:
    treatment_days = {0, 2, 3, 6, 8, 10, 13}
    return [
        {
            "day": index + 1,
            "date": (start + timedelta(days=index)).isoformat(),
            "treatment": index in treatment_days,
            "label": "提醒日" if index in treatment_days else "常规日",
        }
        for index in range(14)
    ]


def seed_db() -> None:
    with SessionLocal() as db:
        if db.get(UserProfile, "demo-user") is None:
            db.add(
                UserProfile(
                    id="demo-user",
                    nickname="林同学（合成）",
                    role="participant",
                    age_range="25-34",
                    goal="改善晚餐后的活动习惯",
                    sleep_schedule="通常 23:30 入睡，07:00 起床",
                    activity_baseline="工作日以久坐为主，晚餐后可安排轻量活动",
                    constraints="仅使用合成资料；不调整药物或治疗安排",
                    preferences="希望每天记录不超过 1 分钟",
                )
            )

        if db.get(UserProfile, "demo-reviewer") is None:
            db.add(
                UserProfile(
                    id="demo-reviewer",
                    nickname="审核员（合成）",
                    role="reviewer",
                    age_range="not_applicable",
                    goal="查看最小化安全审计事件",
                )
            )

        for action_data in ACTION_SEEDS:
            if db.get(ActionTemplate, action_data["id"]) is None:
                db.add(ActionTemplate(**action_data))
        db.flush()

        report = db.get(HealthReport, "demo-report")
        if report is None:
            report = HealthReport(
                id="demo-report",
                user_id="demo-user",
                filename="合成体检报告_001.pdf",
                source="synthetic",
                status="confirmed",
                storage_provider="synthetic_seed",
                content_type="application/pdf",
                ocr_provider="synthetic_seed",
                ocr_status="completed",
                ocr_attempts=1,
                ocr_page_count=1,
            )
            db.add(report)
            db.flush()
            metrics = [
                ("bmi", "身体质量指数", 25.8, "kg/m²", "18.5-23.9", "attention"),
                ("fasting_glucose", "空腹血糖", 6.2, "mmol/L", "3.9-6.1", "attention"),
                ("triglyceride", "甘油三酯", 1.9, "mmol/L", "0.45-1.69", "attention"),
                ("hdl_c", "高密度脂蛋白", 1.18, "mmol/L", ">=1.0", "normal"),
                ("systolic_bp", "收缩压", 128, "mmHg", "90-139", "normal"),
            ]
            for code, name, value, unit, reference, flag in metrics:
                db.add(
                    HealthMetric(
                        report_id=report.id,
                        user_id="demo-user",
                        code=code,
                        name=name,
                        value=value,
                        unit=unit,
                        reference_range=reference,
                        flag=flag,
                        confirmed=True,
                        review_status="confirmed",
                        raw_text=f"{name} {value:g} {unit} 参考 {reference}",
                        extracted_value=value,
                        extracted_unit=unit,
                        extracted_reference_range=reference,
                        confidence=0.99,
                        source_page=1,
                        source_bbox=[0.1, 0.1, 0.3, 0.05],
                    )
                )

        existing_experiment = db.scalar(
            select(Experiment).where(Experiment.user_id == "demo-user").limit(1)
        )
        if existing_experiment is None:
            start = date.today() - timedelta(days=5)
            experiment = Experiment(
                id="demo-experiment",
                user_id="demo-user",
                action_id="action-postmeal-walk",
                status="active",
                start_date=start,
                end_date=start + timedelta(days=13),
                randomization_seed=240917,
                schedule=_demo_schedule(start),
            )
            db.add(experiment)
            db.flush()
            demo_steps = [1680, 720, 1540, 1810, 840]
            treatment_days = {0, 2, 3}
            for index, steps in enumerate(demo_steps):
                db.add(
                    Observation(
                        experiment_id=experiment.id,
                        observed_on=start + timedelta(days=index),
                        treatment=index in treatment_days,
                        completed=True,
                        steps_30m=steps,
                        sleep_hours=[7.2, 6.4, 7.6, 6.9, 7.1][index],
                        subjective_score=[4, 3, 4, 4, 3][index],
                        notes="合成演示记录",
                    )
                )
        db.commit()
