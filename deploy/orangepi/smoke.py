"""Check the board's H5 and API through the same Nginx entry point."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse


def load_api_smoke():
    path = Path(__file__).resolve().parents[1] / "m14" / "smoke.py"
    spec = importlib.util.spec_from_file_location("yunsync_api_smoke", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_board(base_url: str, wait_seconds: float = 0) -> dict:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.query or parsed.fragment:
        raise ValueError("base URL must be an HTTP(S) entry point without a query or fragment")
    base_url = base_url.rstrip("/")
    api = load_api_smoke()
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            dependencies = api.fetch_json(f"{base_url}/api/health").get("dependencies", {})
            database = dependencies.get("database", {})
            cache = dependencies.get("cache", {})
            if database.get("kind") != "postgresql" or database.get("status") != "ok":
                raise RuntimeError("board PostgreSQL is not healthy")
            if cache.get("backend") != "redis" or cache.get("status") != "ok":
                raise RuntimeError("board Redis is not healthy")
            break
        except (OSError, RuntimeError, ValueError):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            time.sleep(min(2, remaining))

    result = api.smoke(f"{base_url}/api", base_url, None, strict=False)
    result["checks"] = ["h5_entry" if name == "h5_https" else name for name in result["checks"]]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--wait-seconds", type=int, default=0)
    args = parser.parse_args()
    try:
        print(json.dumps(check_board(args.base_url, args.wait_seconds), ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"result": "fail", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
