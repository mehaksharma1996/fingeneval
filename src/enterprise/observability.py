"""Structured logging, correlation IDs, and lightweight Prometheus exposition."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import Counter, defaultdict
from collections.abc import MutableMapping

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("fingeneval.enterprise")
REQUESTS: Counter[str] = Counter()
FAILURES: Counter[str] = Counter()
LATENCY_SUM: MutableMapping[str, float] = defaultdict(float)


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            FAILURES[request.url.path] += 1
            raise
        elapsed = time.perf_counter() - started
        REQUESTS[request.url.path] += 1
        LATENCY_SUM[request.url.path] += elapsed
        response.headers["X-Correlation-Id"] = correlation_id
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round(elapsed * 1000, 2),
                    "correlation_id": correlation_id,
                }
            )
        )
        return response


def prometheus_metrics() -> str:
    lines = [
        "# HELP fingeneval_http_requests_total Total HTTP requests.",
        "# TYPE fingeneval_http_requests_total counter",
    ]
    for path, count in sorted(REQUESTS.items()):
        safe = path.replace('"', "")
        lines.append(f'fingeneval_http_requests_total{{path="{safe}"}} {count}')
        lines.append(f'fingeneval_http_failures_total{{path="{safe}"}} {FAILURES[path]}')
        lines.append(f'fingeneval_http_latency_seconds_sum{{path="{safe}"}} {LATENCY_SUM[path]:.6f}')
    return "\n".join(lines) + "\n"
