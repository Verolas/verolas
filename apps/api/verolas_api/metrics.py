"""Prometheus metrics, including the SLA tier histograms.

The bible defines four performance tiers for workflows:
- Tier 1 (interactive): p95 < 30 seconds
- Tier 2 (heavy interactive): p95 < 5 minutes
- Tier 3 (deliverable):  p95 < 30 minutes
- Tier 4 (long compute):  p95 < 60 minutes

Each route declares its tier with the `sla_tier()` decorator from
verolas_api.middleware.sla. The SLA middleware records the request duration
into the matching histogram, labelled by the route path.
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

# Buckets in seconds matching the tier ceilings plus useful intermediates.
# Histograms record observations across all buckets so quantiles can be
# computed per tier.
_BUCKETS_SECONDS = (
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,  # Tier 1 ceiling
    60.0,
    120.0,
    300.0,  # Tier 2 ceiling
    600.0,
    1800.0,  # Tier 3 ceiling
    3600.0,  # Tier 4 ceiling
)


def build_metrics_registry() -> tuple[CollectorRegistry, Histogram, Counter, Counter]:
    """Return a registry plus the metrics handles the app records into.

    The registry is rebuilt per app factory call so tests do not accumulate
    metrics across test cases.
    """
    registry = CollectorRegistry()

    request_duration = Histogram(
        "verolas_request_duration_seconds",
        "Time spent processing requests, labelled by SLA tier and route.",
        labelnames=("tier", "method", "route", "status"),
        buckets=_BUCKETS_SECONDS,
        registry=registry,
    )
    requests_total = Counter(
        "verolas_requests_total",
        "Total request count by route and status.",
        labelnames=("tier", "method", "route", "status"),
        registry=registry,
    )
    sla_violations = Counter(
        "verolas_sla_violations_total",
        "Requests whose duration exceeded the declared tier ceiling.",
        labelnames=("tier", "method", "route"),
        registry=registry,
    )
    return registry, request_duration, requests_total, sla_violations


def render_metrics(registry: CollectorRegistry) -> bytes:
    """Render the registry into the Prometheus exposition format."""
    return generate_latest(registry)


TIER_CEILINGS_SECONDS: dict[int, float] = {
    1: 30.0,
    2: 300.0,
    3: 1800.0,
    4: 3600.0,
}
