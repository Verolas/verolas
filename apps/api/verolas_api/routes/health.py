"""Liveness, readiness, and Prometheus exposition endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST

from verolas_api.metrics import render_metrics
from verolas_api.middleware import sla_tier

router = APIRouter(tags=["system"])


@router.get("/healthz")
@sla_tier(1)
async def healthz() -> dict[str, str]:
    """Always 200 while the process is alive. Used by k8s liveness probe."""
    return {"status": "ok"}


@router.get("/readyz")
@sla_tier(1)
async def readyz() -> dict[str, str]:
    """Returns 200 when the app is ready to serve traffic.

    Today the only readiness gate is that the token verifier and settings
    loaded cleanly. Once the database connection joins the readiness check,
    a DB ping is added here. Used by k8s readiness probe.
    """
    return {"status": "ready"}


@router.get("/metrics")
@sla_tier(1)
async def metrics(request: Request) -> Response:
    """Prometheus scrape endpoint."""
    registry = request.app.state.metrics_registry
    body = render_metrics(registry)
    return Response(content=body, media_type=CONTENT_TYPE_LATEST)
