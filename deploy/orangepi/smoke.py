"""Check the board's H5 and API through the same Nginx entry point."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen


def load_api_smoke():
    path = Path(__file__).resolve().parents[1] / "m14" / "smoke.py"
    spec = importlib.util.spec_from_file_location("yunsync_api_smoke", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EntryAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.styles = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("type") == "module" and attrs.get("src"):
            self.scripts.append(attrs["src"])
        if tag == "link" and "stylesheet" in attrs.get("rel", "").split() and attrs.get("href"):
            self.styles.append(attrs["href"])


def check_h5(base_url):
    assets = EntryAssets()
    with urlopen(base_url, timeout=12) as entry:
        if entry.headers.get_content_type() != "text/html":
            raise RuntimeError("H5 entry is not HTML")
        assets.feed(entry.read(250_000).decode("utf-8"))
    if not assets.scripts or not assets.styles:
        raise RuntimeError("H5 entry has no application script or stylesheet")
    for paths, types in ((assets.scripts, {"application/javascript", "text/javascript"}),
                         (assets.styles, {"text/css"})):
        for path in paths:
            url = urljoin(base_url + "/", path)
            if urlparse(url)[:2] != urlparse(base_url)[:2]:
                raise RuntimeError("H5 entry references an asset outside the board")
            with urlopen(url, timeout=12) as asset:
                if asset.headers.get_content_type() not in types or not asset.read(1):
                    raise RuntimeError(f"invalid H5 asset: {path}")


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

    check_h5(base_url)
    result = api.smoke(f"{base_url}/api", None, None, strict=False, verify_recipe=True)
    if result["database"] != "ok" or result["cache"] != "ok":
        raise RuntimeError("board dependencies degraded during acceptance")
    result["checks"].extend(["h5_entry", "h5_assets"])
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
