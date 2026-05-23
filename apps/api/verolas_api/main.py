"""Verolas API app factory.

The factory builds a fresh FastAPI app with a fresh metrics registry per
call so tests can spin up isolated apps without metrics bleeding across
fixtures. The production entrypoint at the bottom assembles the default
app from environment settings.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import CollectorRegistry
from verolas_auth import TokenVerifier, TokenVerifierSettings
from verolas_storage import PresignedUrlService, StorageSettings

from verolas_api import __version__
from verolas_api.logging import configure_logging
from verolas_api.metrics import build_metrics_registry
from verolas_api.middleware import RequestIdMiddleware, SlaTierMiddleware
from verolas_api.routes import health
from verolas_api.routes.v1 import api_v1
from verolas_api.settings import Settings


def create_app(
    *,
    settings: Settings | None = None,
    token_verifier: TokenVerifier | None = None,
    metrics_registry: CollectorRegistry | None = None,
    storage_service: PresignedUrlService | None = None,
) -> FastAPI:
    """Build a new app instance.

    `settings`, `token_verifier`, `metrics_registry`, and `storage_service`
    are injectable for tests. In production, leave them None to load from
    environment.
    """
    actual_settings = settings or Settings()
    configure_logging(actual_settings.log_level, actual_settings.log_json)

    if metrics_registry is None:
        registry, duration, requests_total, sla_violations = build_metrics_registry()
    else:
        registry, duration, requests_total, sla_violations = (
            metrics_registry,
            *build_metrics_registry()[1:],  # mypy friendly tuple expansion
        )

    if token_verifier is None:
        token_verifier = TokenVerifier(
            TokenVerifierSettings(
                issuer=actual_settings.oidc_issuer,
                audience=actual_settings.oidc_audience,
                jwks_cache_ttl_seconds=actual_settings.oidc_jwks_cache_ttl_seconds,
            )
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        yield

    app = FastAPI(
        title="Verolas API",
        version=__version__,
        description="Verolas backend gateway.",
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    if storage_service is None and actual_settings.storage_access_key_id:
        storage_service = PresignedUrlService(
            StorageSettings(
                endpoint_url=actual_settings.storage_endpoint_url,
                region=actual_settings.storage_region,
                access_key_id=actual_settings.storage_access_key_id,
                secret_access_key=actual_settings.storage_secret_access_key,
                bucket=actual_settings.storage_bucket,
                presign_expiry_seconds=actual_settings.storage_presign_expiry_seconds,
            )
        )

    app.state.settings = actual_settings
    app.state.token_verifier = token_verifier
    app.state.metrics_registry = registry
    app.state.storage_service = storage_service

    app.add_middleware(
        SlaTierMiddleware,
        request_duration=duration,
        requests_total=requests_total,
        sla_violations=sla_violations,
    )
    app.add_middleware(RequestIdMiddleware)

    app.include_router(health.router)
    app.include_router(api_v1)

    return app


app = create_app()
