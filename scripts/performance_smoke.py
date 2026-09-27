from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from math import ceil
from pathlib import Path
import re
from time import perf_counter

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{16,4096}$")


def percentile_nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("values cannot be empty")
    ordered = sorted(values)
    rank = max(ceil(percentile / 100 * len(ordered)) - 1, 0)
    return ordered[rank]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a local synthetic concurrency smoke test against YunSync."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--p95-limit-ms", type=float, default=500.0)
    parser.add_argument("--core-p95-limit-ms", type=float, default=2500.0)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--account-id", default="demo-student")
    parser.add_argument("--tokens-file", type=Path)
    parser.add_argument("--ordinary-path", default="/api/v1/account/status")
    parser.add_argument("--core-path", default="/api/v1/dashboard")
    return parser.parse_args()


def load_external_tokens(path: Path, required: int) -> list[str]:
    resolved = path.resolve()
    if resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError("tokens file must stay outside the repository")
    tokens = [line.strip() for line in resolved.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(tokens) < required or any(not TOKEN_PATTERN.fullmatch(token) for token in tokens):
        raise ValueError("tokens file does not contain enough valid bearer tokens")
    return tokens[:required]


def summarize_results(
    results: list[tuple[int, float]], *, elapsed_seconds: float
) -> dict[str, object]:
    status_counts: dict[str, int] = {}
    durations: list[float] = []
    errors = 0
    for status_code, duration_ms in results:
        key = str(status_code)
        status_counts[key] = status_counts.get(key, 0) + 1
        durations.append(duration_ms)
        if status_code < 200 or status_code >= 400:
            errors += 1
    return {
        "requests": len(results),
        "status_counts": status_counts,
        "error_rate": round(errors / len(results), 6) if results else 1.0,
        "p50_ms": round(percentile_nearest_rank(durations, 50), 2),
        "p95_ms": round(percentile_nearest_rank(durations, 95), 2),
        "p99_ms": round(percentile_nearest_rank(durations, 99), 2),
        "max_ms": round(max(durations), 2),
        "throughput_rps": round(len(results) / max(elapsed_seconds, 0.000001), 2),
    }


def run(args: argparse.Namespace) -> tuple[dict[str, object], bool]:
    if args.concurrency < 1 or args.requests < args.concurrency:
        raise ValueError("requests must be greater than or equal to concurrency")
    if not 0 <= args.max_error_rate <= 1:
        raise ValueError("max-error-rate must be between 0 and 1")
    if not args.base_url.startswith(("http://", "https://")):
        raise ValueError("base-url must use http:// or https://")
    if args.base_url.startswith("http://") and not args.base_url.startswith(
        ("http://127.0.0.1", "http://localhost", "http://[::1]")
    ):
        raise ValueError("remote performance targets must use https")
    if any(not value.startswith("/") or ".." in value for value in (args.ordinary_path, args.core_path)):
        raise ValueError("endpoint paths must be absolute and must not contain traversal")

    limits = httpx.Limits(
        max_connections=max(args.concurrency, 20),
        max_keepalive_connections=max(args.concurrency, 20),
    )
    with httpx.Client(
        base_url=args.base_url.rstrip("/"),
        timeout=10,
        trust_env=False,
        limits=limits,
    ) as client:
        if args.tokens_file:
            tokens = load_external_tokens(args.tokens_file, args.concurrency)
            credential_mode = "external_tokens"
        else:
            tokens = []
            credential_mode = "synthetic_demo"
            for _ in range(args.concurrency):
                response = client.post(
                    "/api/v1/auth/demo", json={"account_id": args.account_id}
                )
                response.raise_for_status()
                tokens.append(response.json()["access_token"])

            participant_headers = {"Authorization": f"Bearer {tokens[0]}"}
            notice_response = client.get("/api/v1/consents/notice")
            notice_response.raise_for_status()
            consent_response = client.post(
                "/api/v1/consents/accept",
                json={"version": notice_response.json()["version"]},
                headers=participant_headers,
            )
            consent_response.raise_for_status()

        def timed_get(path: str, index: int) -> tuple[int, float]:
            started_at = perf_counter()
            response = client.get(
                path,
                headers={"Authorization": f"Bearer {tokens[index % len(tokens)]}"},
            )
            duration_ms = (perf_counter() - started_at) * 1000
            return response.status_code, duration_ms

        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            ordinary_started = perf_counter()
            ordinary_results = list(
                pool.map(
                    lambda index: timed_get(args.ordinary_path, index),
                    range(args.requests),
                )
            )
            ordinary_elapsed = perf_counter() - ordinary_started
            core_started = perf_counter()
            core_results = list(
                pool.map(
                    lambda index: timed_get(args.core_path, index),
                    range(args.concurrency),
                )
            )
            core_elapsed = perf_counter() - core_started

    ordinary = summarize_results(ordinary_results, elapsed_seconds=ordinary_elapsed)
    core = summarize_results(core_results, elapsed_seconds=core_elapsed)
    passed = (
        float(ordinary["error_rate"]) <= args.max_error_rate
        and float(ordinary["p95_ms"]) < args.p95_limit_ms
        and float(core["error_rate"]) <= args.max_error_rate
        and float(core["p95_ms"]) < args.core_p95_limit_ms
    )
    report: dict[str, object] = {
        "version": "m10-performance-evidence-v2",
        "mode": credential_mode,
        "sessions": args.concurrency,
        "ordinary_endpoint": args.ordinary_path,
        "ordinary_requests": args.requests,
        "ordinary_status_counts": ordinary["status_counts"],
        "ordinary_p50_ms": ordinary["p50_ms"],
        "ordinary_p95_ms": ordinary["p95_ms"],
        "ordinary_p99_ms": ordinary["p99_ms"],
        "ordinary_error_rate": ordinary["error_rate"],
        "ordinary_throughput_rps": ordinary["throughput_rps"],
        "p95_limit_ms": args.p95_limit_ms,
        "core_endpoint": args.core_path,
        "core_requests": args.concurrency,
        "core_status_counts": core["status_counts"],
        "core_p50_ms": core["p50_ms"],
        "core_p95_ms": core["p95_ms"],
        "core_p99_ms": core["p99_ms"],
        "core_error_rate": core["error_rate"],
        "core_throughput_rps": core["throughput_rps"],
        "core_p95_limit_ms": args.core_p95_limit_ms,
        "max_error_rate": args.max_error_rate,
        "passed": passed,
    }
    return report, passed


def main() -> int:
    try:
        report, passed = run(parse_args())
    except httpx.HTTPStatusError as exc:
        print(
            json.dumps(
                {
                    "passed": False,
                    "error": "HTTPStatusError",
                    "status_code": exc.response.status_code,
                    "path": exc.request.url.path,
                },
                sort_keys=True,
            )
        )
        return 2
    except (ValueError, httpx.HTTPError, KeyError) as exc:
        print(json.dumps({"passed": False, "error": type(exc).__name__}))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
