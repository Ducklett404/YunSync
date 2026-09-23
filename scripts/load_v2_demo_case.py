from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.core.demo_case import validate_demo_case  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.health import HealthMetric, HealthReport  # noqa: E402
from app.models.user import UserProfile  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="把 M8 双报告合成案例装载到非生产数据库。")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "demo" / "v2_m8_demo_case.json",
    )
    args = parser.parse_args()
    if settings.environment == "production":
        raise SystemExit("拒绝向 Production 装载合成演示数据。")
    validation = validate_demo_case(args.manifest)
    if not validation["valid"]:
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 2
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    created_reports = 0
    with SessionLocal() as db:
        participant_id = payload["account"]["participant_id"]
        if db.get(UserProfile, participant_id) is None:
            db.add(
                UserProfile(
                    id=participant_id,
                    nickname="M8 合成演示用户",
                    role="participant",
                    goal="演示两次报告的食养随访闭环",
                    constraints="仅使用合成数据；不替代专业意见",
                )
            )
            db.flush()
        for item in payload["reports"]:
            if db.get(HealthReport, item["id"]) is not None:
                continue
            examined_at = datetime.fromisoformat(item["exam_date"]).replace(tzinfo=timezone.utc)
            report = HealthReport(
                id=item["id"],
                user_id=participant_id,
                filename=f"{item['id']}-synthetic.json",
                institution=item["institution"],
                examined_at=examined_at,
                source="synthetic_m8_demo",
                status="confirmed",
                critical_marker_status=item["critical_value_status"],
                critical_marker_reviewed_at=examined_at,
                storage_provider="synthetic_seed",
                content_type="application/json",
                ocr_provider="manual_synthetic",
                ocr_status="completed",
                ocr_attempts=1,
                ocr_page_count=1,
                processed_at=examined_at,
                created_at=examined_at,
            )
            db.add(report)
            db.flush()
            for metric in item["metrics"]:
                db.add(
                    HealthMetric(
                        report_id=report.id,
                        user_id=participant_id,
                        code=metric["code"],
                        name=metric["name"],
                        value=metric["value"],
                        unit=metric["unit"],
                        reference_range=metric["reference_range"],
                        method=metric["method"],
                        confirmed=True,
                        review_status="confirmed",
                        raw_text="合成演示结构化指标",
                        extracted_value=metric["value"],
                        extracted_unit=metric["unit"],
                        extracted_reference_range=metric["reference_range"],
                        confidence=1.0,
                        measured_at=examined_at,
                    )
                )
            created_reports += 1
        db.commit()
    print(
        json.dumps(
            {
                "status": "loaded",
                "synthetic": True,
                "created_reports": created_reports,
                "total_reports": validation["report_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
