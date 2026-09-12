from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.core.cloud_readiness import build_cloud_readiness  # noqa: E402
from app.core.config import Settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查 YunSync 云环境配置，不连接或修改任何云资源。"
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=PROJECT_ROOT / ".env",
        help="要检查的环境变量文件；默认读取项目根目录 .env。",
    )
    args = parser.parse_args()

    try:
        settings = Settings(_env_file=args.env_file)
    except ValidationError as exc:
        safe_errors = [
            {"field": ".".join(map(str, item["loc"])), "message": item["msg"]}
            for item in exc.errors(include_input=False, include_url=False)
        ]
        print(json.dumps({"ready": False, "validation_errors": safe_errors}, ensure_ascii=False, indent=2))
        return 2

    report = build_cloud_readiness(settings)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
