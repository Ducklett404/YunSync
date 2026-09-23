from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.core.demo_case import validate_demo_case  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 M8 V2 双报告合成演示案例。")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "demo" / "v2_m8_demo_case.json",
    )
    args = parser.parse_args()
    report = validate_demo_case(args.manifest)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
