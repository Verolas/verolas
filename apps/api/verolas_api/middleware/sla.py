"""SLA tier annotation and middleware.

Each route's endpoint function is decorated with `sla_tier(N)` to declare its
performance tier (1 to 4). The middleware reads the tier off the matched
route, records the request duration into the Prometheus histogram, and
increments a counter when the duration exceeds the tier ceiling.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

import structlog
from fastapi import Request, Response
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

from verolas_api.metrics import TIER_CEILINGS_SECONDS

F = TypeVar("F", bound=Callable[..., object])

_SLA_TIER_ATTR = "__verolas_sla_tier__"

logger = structlog.get_logger(__name__)


def sla_tier(tier: int) -> Callable[[F], F]:
    """Decorate an endpoint with its SLA tier.

    Usage:

        @router.get("/foo")
        @sla_tier(1)
        async def foo() -> dict[str, str]:
            return {"hello": "world"}

    The middleware reads this attribute off the endpoint to record metrics
    and enforce the ceiling. Tier must be 1, 2, 3, or 4.
    """
    if tier not in TIER_CEILINGS_SECONDS:
        raise ValueError(f"SLA tier must be one of {sorted(TIER_CEILINGS_SECONDS)}; got {tier}")

    def decorator(func: F) -> F:
        setattr(func, _SLA_TIER_ATTR, tier)
        return func

    return decorator


def get_tier(endpoint: object) -> int | None:
    """Return the declared SLA tier on a route endpoint, or None if missing."""
    value = getattr(endpoint, _SLA_TIER_ATTR, None)
    if isinstance(value, int):
        return value
    return None


class SlaTierMiddleware(BaseHTTPMiddleware):
    """Time every request and record its duration under the matched tier."""

    def __init__(
        self,
        app: object,
        *,
        request_duration: Histogram,
        requests_total: Counter,
        sla_violations: Counter,
        unknown_tier_default: int = 1,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._duration = request_duration
        self._counter = requests_total
        self._violations = sla_violations
        self._unknown_default = unknown_tier_default

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        route = request.scope.get("route")
        endpoint = getattr(route, "endpoint", None)
        tier = get_tier(endpoint) if endpoint is not None else None
        if tier is None:
            tier = self._unknown_default

        route_path: str = getattr(route, "path", request.url.path)
        labels = {
            "tier": str(tier),
            "method": request.method,
            "route": route_path,
            "status": str(response.status_code),
        }
        self._duration.labels(**labels).observe(elapsed)
        self._counter.labels(**labels).inc()

        ceiling = TIER_CEILINGS_SECONDS.get(tier)
        if ceiling is not None and elapsed > ceiling:
            self._violations.labels(
                tier=str(tier),
                method=request.method,
                route=route_path,
            ).inc()
            logger.warning(
                "sla_violation",
                tier=tier,
                ceiling_seconds=ceiling,
                elapsed_seconds=elapsed,
                method=request.method,
                route=route_path,
                status=response.status_code,
            )

        return response
