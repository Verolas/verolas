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
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CollectorRegistry
from psycopg_pool import AsyncConnectionPool
from verolas_auth import TokenVerifier, TokenVerifierSettings
from verolas_storage import PresignedUrlService, StorageSettings

from verolas_api import __version__
from verolas_api.logging import configure_logging
from verolas_api.metrics import build_metrics_registry
from verolas_api.middleware import RequestIdMiddleware, SlaTierMiddleware
from verolas_api.routes import health
from verolas_api.routes.v1 import api_v1
from verolas_api.settings import Settings
from verolas_api.vendors import bootstrap_vendors
from verolas_api.workflow import bootstrap_workflow_templates
from verolas_api.workflow.sync import sync_code_templates

# Force vendor adapters to register their fetchers with
# verolas_api.connector_instances before the first request.
bootstrap_vendors()

# Force workflow template modules to register with the in-process
# registry. Sync to Postgres happens inside the lifespan once the pool
# is open.
bootstrap_workflow_templates()


def create_app(
    *,
    settings: Settings | None = None,
    token_verifier: TokenVerifier | None = None,
    metrics_registry: CollectorRegistry | None = None,
    storage_service: PresignedUrlService | None = None,
    db_pool: AsyncConnectionPool | None = None,
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
        import httpx

        token_verifier = TokenVerifier(
            TokenVerifierSettings(
                issuer=actual_settings.oidc_issuer,
                audience=actual_settings.oidc_audience,
                jwks_cache_ttl_seconds=actual_settings.oidc_jwks_cache_ttl_seconds,
            ),
            http_client=httpx.Client(verify=actual_settings.oidc_verify_tls, timeout=5.0),
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Open the DB pool if a URL is configured and one wasn't injected.
        owns_pool = False
        if db_pool is None and actual_settings.database_url:
            pool = AsyncConnectionPool(
                conninfo=actual_settings.database_url,
                min_size=1,
                max_size=10,
                open=False,
            )
            await pool.open()
            await pool.wait()
            app.state.db_pool = pool
            owns_pool = True
        elif db_pool is not None:
            app.state.db_pool = db_pool

        # Sync code-authored workflow templates into Postgres. This is
        # idempotent: unchanged templates produce no new version rows.
        if hasattr(app.state, "db_pool"):
            try:
                await sync_code_templates(app.state.db_pool)
            except Exception:
                # Sync failure should not prevent the app from booting;
                # the existing templates in DB remain available. Log the
                # exception and continue.
                import logging as _logging

                _logging.getLogger(__name__).exception("workflow_template_sync.failed")

        try:
            yield
        finally:
            if owns_pool:
                await app.state.db_pool.close()

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
    if db_pool is not None:
        app.state.db_pool = db_pool

    app.add_middleware(
        SlaTierMiddleware,
        request_duration=duration,
        requests_total=requests_total,
        sla_violations=sla_violations,
    )
    app.add_middleware(RequestIdMiddleware)
    if actual_settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=actual_settings.cors_allow_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
            max_age=600,
        )

    app.include_router(health.router)
    app.include_router(api_v1)

    return app


app = create_app()
