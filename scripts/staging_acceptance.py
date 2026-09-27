"""Run read-only HTTPS and edge-security checks against a deployed YunSync target."""

from __future__ import annotations

import argparse
import json
import ssl
from datetime import datetime, timezone
from pathlib import Path
import socket
from urllib.parse import urlparse, urlunparse

import httpx


REQUIRED_SECURITY_HEADERS = {
    "cache-control": "no-store",
    "content-security-policy": "default-src",
    "permissions-policy": "camera=()",
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
}


def validate_base_url(value: str, *, allow_http_local: bool = False) -> str:
    parsed = urlparse(value.strip())
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base-url must not contain credentials, query, or fragment")
    if not parsed.hostname or parsed.path not in {"", "/"}:
        raise ValueError("base-url must contain only scheme, host, and optional port")
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (
        allow_http_local and parsed.scheme == "http" and local
    ):
        raise ValueError("remote acceptance targets must use https")
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def response_checks(
    *, path: str, status_code: int, headers: dict[str, str], expected_status: int
) -> list[dict[str, object]]:
    normalized = {key.lower(): value for key, value in headers.items()}
    checks: list[dict[str, object]] = [
        {
            "code": f"{path}:status",
            "passed": status_code == expected_status,
            "observed": status_code,
        },
        {
            "code": f"{path}:request-id",
            "passed": bool(normalized.get("x-request-id", "").strip()),
        },
    ]
    for header, marker in REQUIRED_SECURITY_HEADERS.items():
        value = normalized.get(header, "")
        checks.append(
            {
                "code": f"{path}:header:{header}",
                "passed": marker.lower() in value.lower(),
            }
        )
    return checks


def inspect_tls(base_url: str, timeout: float) -> dict[str, object]:
    parsed = urlparse(base_url)
    if parsed.scheme != "https":
        return {"checked": False, "passed": True, "reason": "local_http_override"}
    context = ssl.create_default_context()
    with socket.create_connection((parsed.hostname, parsed.port or 443), timeout=timeout) as raw:
        with context.wrap_socket(raw, server_hostname=parsed.hostname) as secured:
            certificate = secured.getpeercert()
            expires_raw = certificate.get("notAfter")
            if not isinstance(expires_raw, str):
                raise ssl.SSLError("certificate expiry missing")
            expires_at = datetime.strptime(expires_raw, "%b %d %H:%M:%S %Y %Z").replace(
                tzinfo=timezone.utc
            )
            remaining_days = int(
                (expires_at - datetime.now(timezone.utc)).total_seconds() // 86400
            )
            return {
                "checked": True,
                "passed": remaining_days >= 14,
                "tls_version": secured.version(),
                "certificate_days_remaining": remaining_days,
            }


def run(base_url: str, *, timeout: float, allow_http_local: bool) -> dict[str, object]:
    target = validate_base_url(base_url, allow_http_local=allow_http_local)
    checks: list[dict[str, object]] = []
    with httpx.Client(base_url=target, timeout=timeout, trust_env=False) as client:
        for path, expected in (
            ("/healthz", 200),
            ("/readyz", 200),
            ("/api/v1/account/status", 401),
        ):
            response = client.get(path)
            checks.extend(
                response_checks(
                    path=path,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    expected_status=expected,
                )
            )
            if path == "/readyz" and response.status_code == 200:
                try:
                    ready = response.json()
                except ValueError:
                    ready = {}
                checks.append(
                    {
                        "code": "/readyz:dependency-status",
                        "passed": ready.get("status") == "ready"
                        and ready.get("dependencies", {}).get("database") == "ready",
                    }
                )

        if target.startswith("https://"):
            http_target = "http://" + target.removeprefix("https://")
            redirect = httpx.get(
                http_target + "/api/v1/account/status",
                timeout=timeout,
                follow_redirects=False,
                trust_env=False,
            )
            location = redirect.headers.get("location", "")
            checks.append(
                {
                    "code": "http-to-https-redirect",
                    "passed": redirect.status_code in {301, 302, 307, 308}
                    and location.startswith(target + "/"),
                    "observed": redirect.status_code,
                }
            )

    tls = inspect_tls(target, timeout)
    checks.append({"code": "tls-certificate", "passed": tls["passed"]})
    return {
        "version": "m10-staging-acceptance-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_scheme": urlparse(target).scheme,
        "passed": all(bool(item["passed"]) for item in checks),
        "summary": {
            "passed": sum(bool(item["passed"]) for item in checks),
            "total": len(checks),
        },
        "tls": tls,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="执行 M10 Staging 只读 HTTPS 验收。")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--allow-http-local", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = run(
            args.base_url,
            timeout=args.timeout,
            allow_http_local=args.allow_http_local,
        )
    except (ValueError, httpx.HTTPError, OSError, ssl.SSLError) as exc:
        report = {
            "version": "m10-staging-acceptance-v1",
            "passed": False,
            "error": type(exc).__name__,
        }
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
