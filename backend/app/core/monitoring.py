from __future__ import annotations

from collections import defaultdict
from threading import RLock

from fastapi import Request


LATENCY_BUCKETS_MS = (50, 100, 250, 500, 1000, 2500, 5000)


def normalized_route(request: Request) -> str:
    """Return a bounded route label without object IDs or query values."""
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str) and template.startswith("/"):
        return template
    if request.url.path in {"/healthz", "/readyz", "/internal/metrics"}:
        return request.url.path
    if request.url.path.startswith("/api/"):
        return "/api/__blocked_or_unmatched__"
    return "/__unmatched__"


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class MonitoringRegistry:
    """Small in-process Prometheus registry with bounded HTTP label values."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._requests: dict[tuple[str, str, str], int] = defaultdict(int)
            self._duration_count: dict[tuple[str, str], int] = defaultdict(int)
            self._duration_sum: dict[tuple[str, str], float] = defaultdict(float)
            self._duration_buckets: dict[tuple[str, str, int], int] = defaultdict(int)
            self._events: dict[str, int] = defaultdict(int)

    def record(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
        slow_threshold_ms: int,
    ) -> None:
        method = method.upper()[:12]
        status_class = f"{status_code // 100}xx"
        key = (method, route, status_class)
        route_key = (method, route)
        with self._lock:
            self._requests[key] += 1
            self._duration_count[route_key] += 1
            self._duration_sum[route_key] += duration_ms
            for bucket in LATENCY_BUCKETS_MS:
                if duration_ms <= bucket:
                    self._duration_buckets[(method, route, bucket)] += 1
            if status_code >= 500:
                self._events["failed"] += 1
            if status_code == 429:
                self._events["rate_limited"] += 1
            if duration_ms >= slow_threshold_ms:
                self._events["slow"] += 1

    def render_prometheus(self) -> str:
        with self._lock:
            requests = dict(self._requests)
            duration_count = dict(self._duration_count)
            duration_sum = dict(self._duration_sum)
            duration_buckets = dict(self._duration_buckets)
            events = dict(self._events)

        lines = [
            "# HELP yunsync_http_requests_total HTTP requests by bounded route template.",
            "# TYPE yunsync_http_requests_total counter",
        ]
        for (method, route, status_class), value in sorted(requests.items()):
            labels = (
                f'method="{_escape_label(method)}",route="{_escape_label(route)}",'
                f'status_class="{status_class}"'
            )
            lines.append(f"yunsync_http_requests_total{{{labels}}} {value}")

        lines.extend(
            [
                "# HELP yunsync_http_request_duration_ms Request duration in milliseconds.",
                "# TYPE yunsync_http_request_duration_ms histogram",
            ]
        )
        for method, route in sorted(duration_count):
            base = f'method="{_escape_label(method)}",route="{_escape_label(route)}"'
            for bucket in LATENCY_BUCKETS_MS:
                value = duration_buckets.get((method, route, bucket), 0)
                lines.append(
                    "yunsync_http_request_duration_ms_bucket"
                    f'{{{base},le="{bucket}"}} {value}'
                )
            count = duration_count[(method, route)]
            lines.append(
                "yunsync_http_request_duration_ms_bucket"
                f'{{{base},le="+Inf"}} {count}'
            )
            lines.append(
                f"yunsync_http_request_duration_ms_sum{{{base}}} "
                f"{duration_sum[(method, route)]:.3f}"
            )
            lines.append(f"yunsync_http_request_duration_ms_count{{{base}}} {count}")

        lines.extend(
            [
                "# HELP yunsync_http_events_total HTTP failure, slow and rate-limit events.",
                "# TYPE yunsync_http_events_total counter",
            ]
        )
        for event in ("failed", "rate_limited", "slow"):
            lines.append(f'yunsync_http_events_total{{event="{event}"}} {events.get(event, 0)}')
        return "\n".join(lines) + "\n"


monitoring_registry = MonitoringRegistry()
