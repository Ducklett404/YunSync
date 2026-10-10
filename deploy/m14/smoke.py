"""Post-deploy public smoke test. Prints metadata only, never response bodies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


def fetch_json(url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urlopen(request, timeout=12) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        result = json.load(response)
    if not isinstance(result, dict):
        raise RuntimeError("expected JSON object")
    return result


def check_url(value: str, allow_local_http: bool) -> str:
    parsed = urlparse(value)
    if parsed.scheme == "https" and parsed.netloc:
        return value.rstrip("/")
    if allow_local_http and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}:
        return value.rstrip("/")
    raise ValueError("public endpoints must use HTTPS")


def smoke(api_base: str, h5_url: str | None, expected_sha: str | None, strict: bool) -> dict:
    if strict and (not h5_url or not expected_sha):
        raise ValueError("cloud acceptance requires an H5 URL and exact Git commit ID")
    checks: list[str] = []
    health = fetch_json(f"{api_base}/health")
    if health.get("status") not in ({"ok"} if strict else {"ok", "degraded"}):
        raise RuntimeError("health status is not acceptable")
    if expected_sha and health.get("releaseSha") != expected_sha:
        raise RuntimeError("deployed release SHA does not match the requested commit")
    dependencies = health.get("dependencies", {})
    if strict:
        if dependencies.get("database", {}).get("kind") != "postgresql" or dependencies.get("database", {}).get("status") != "ok":
            raise RuntimeError("RDS PostgreSQL is not healthy")
        if dependencies.get("cache", {}).get("backend") != "redis" or dependencies.get("cache", {}).get("status") != "ok":
            raise RuntimeError("DCS Redis is not healthy")
    checks.append("health")

    context = fetch_json(f"{api_base}/v1/context/today?{urlencode({'city': '北京', 'date': '2026-01-26'})}")
    if context.get("seasonalContent", {}).get("id") != "m2-laba":
        raise RuntimeError("festival context is missing")
    checks.append("festival_context")

    today = fetch_json(f"{api_base}/v1/recommendations/today", {
        "city": "北京", "region": "华北", "date": "2026-01-26", "feelings": ["有点着凉"]
    })
    if not today.get("main", {}).get("id"):
        raise RuntimeError("today recommendation is empty")
    checks.append("today_feeling")

    pantry = fetch_json(f"{api_base}/v1/recommendations/pantry", {
        "ingredients": ["西红柿", "豆腐", "鸡蛋", "食用油"], "tools": ["汤锅", "菜刀"],
        "maxMinutes": 30, "targetServings": 2, "maxAdditionalIngredients": 0
    })
    if not pantry.get("matches"):
        raise RuntimeError("pantry recommendation is empty")
    checks.append("pantry")

    natural = fetch_json(f"{api_base}/v1/recommendations/natural", {
        "text": "有点着凉，想喝粥", "city": "北京", "region": "华北", "date": "2026-01-26"
    })
    if not natural.get("main", {}).get("id"):
        raise RuntimeError("natural recommendation is empty")
    if strict and natural.get("ai", {}).get("status") != "assisted":
        raise RuntimeError("live MaaS assistance was not observed")
    checks.append("natural_language")

    if h5_url:
        with urlopen(Request(h5_url), timeout=12) as response:
            content_type = response.headers.get("Content-Type", "")
            if response.status != 200 or "text/html" not in content_type:
                raise RuntimeError("H5 entry is unavailable")
            if expected_sha and f'<meta name="yunsync-release" content="{expected_sha}">'.encode() not in response.read(250_000):
                raise RuntimeError("H5 release SHA does not match the requested commit")
        checks.append("h5_https")
    return {"result": "pass", "releaseSha": health.get("releaseSha") or None, "checks": checks,
            "database": dependencies.get("database", {}).get("status"),
            "cache": dependencies.get("cache", {}).get("status"),
            "maas": natural.get("ai", {}).get("status")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--h5-url")
    parser.add_argument("--expected-sha")
    parser.add_argument("--allow-degraded", action="store_true", help="Local checks only; not M14 cloud acceptance")
    parser.add_argument("--allow-local-http", action="store_true", help="Only localhost/127.0.0.1")
    args = parser.parse_args()
    try:
        api_base = check_url(args.api_base, args.allow_local_http)
        h5_url = check_url(args.h5_url, args.allow_local_http) if args.h5_url else None
        if args.expected_sha and not re.fullmatch(r"[0-9a-f]{40}", args.expected_sha):
            raise ValueError("expected SHA must be a full Git commit ID")
        print(json.dumps(smoke(api_base, h5_url, args.expected_sha, not args.allow_degraded), ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"result": "fail", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
