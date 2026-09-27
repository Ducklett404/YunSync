"""Validate the repository Prometheus alert baseline without external dependencies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ALERTS = {
    "YunSyncTargetDown": ("up{job=\"yunsync\"}", "critical"),
    "YunSyncHighErrorRate": ("yunsync_http_requests_total", "critical"),
    "YunSyncHighP95Latency": ("histogram_quantile", "warning"),
    "YunSyncRateLimitSpike": ("yunsync_http_events_total", "warning"),
}
FORBIDDEN_LABELS = ("user_id", "report_id", "request_id", "storage_key")


def validate_rules(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for alert, (expression_marker, severity) in EXPECTED_ALERTS.items():
        block_match = re.search(
            rf"- alert:\s*{re.escape(alert)}\s*(.*?)(?=\n\s*- alert:|\Z)",
            text,
            flags=re.DOTALL,
        )
        if not block_match:
            errors.append(f"missing_alert:{alert}")
            continue
        block = block_match.group(1)
        if expression_marker not in block:
            errors.append(f"missing_expression:{alert}")
        if f"severity: {severity}" not in block:
            errors.append(f"missing_severity:{alert}")
        if not re.search(r"\n\s+for:\s+\S+", block):
            errors.append(f"missing_for:{alert}")
    lowered = text.lower()
    for label in FORBIDDEN_LABELS:
        if label in lowered:
            errors.append(f"forbidden_high_cardinality_label:{label}")
    if "change_me" in lowered:
        errors.append("placeholder_value")
    return {
        "status": "passed" if not errors else "failed",
        "rules": len(EXPECTED_ALERTS),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 M10 Prometheus 告警规则。")
    parser.add_argument(
        "--rules",
        type=Path,
        default=PROJECT_ROOT / "deploy" / "prometheus-alerts.yml",
    )
    args = parser.parse_args()
    result = validate_rules(args.rules)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
