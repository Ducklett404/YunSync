from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from math import ceil
from time import perf_counter

import httpx


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
    parser.add_argument("--account-id", default="demo-student")
    return parser.parse_args()


def run(args: argparse.Namespace) -> tuple[dict[str, object], bool]:
    if args.concurrency < 1 or args.requests < args.concurrency:
        raise ValueError("requests must be greater than or equal to concurrency")
    if not args.base_url.startswith(("http://", "https://")):
        raise ValueError("base-url must use http:// or https://")

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
        tokens: list[str] = []
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
            ordinary_results = list(
                pool.map(
                    lambda index: timed_get("/api/v1/account/status", index),
                    range(args.requests),
                )
            )
            core_results = list(
                pool.map(
                    lambda index: timed_get("/api/v1/dashboard", index),
                    range(args.concurrency),
                )
            )

    def summarize(results: list[tuple[int, float]]) -> tuple[dict[str, int], float]:
        status_counts: dict[str, int] = {}
        durations: list[float] = []
        for status_code, duration_ms in results:
            key = str(status_code)
            status_counts[key] = status_counts.get(key, 0) + 1
            durations.append(duration_ms)
        return status_counts, round(percentile_nearest_rank(durations, 95), 2)

    ordinary_status_counts, ordinary_p95_ms = summarize(ordinary_results)
    core_status_counts, core_p95_ms = summarize(core_results)
    passed = (
        ordinary_status_counts == {"200": args.requests}
        and ordinary_p95_ms < args.p95_limit_ms
        and core_status_counts == {"200": args.concurrency}
    )
    report: dict[str, object] = {
        "mode": "local_synthetic_sessions",
        "synthetic_sessions": args.concurrency,
        "ordinary_endpoint": "/api/v1/account/status",
        "ordinary_requests": args.requests,
        "ordinary_status_counts": ordinary_status_counts,
        "ordinary_p95_ms": ordinary_p95_ms,
        "p95_limit_ms": args.p95_limit_ms,
        "core_endpoint": "/api/v1/dashboard",
        "core_requests": args.concurrency,
        "core_status_counts": core_status_counts,
        "core_p95_ms_observed": core_p95_ms,
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
