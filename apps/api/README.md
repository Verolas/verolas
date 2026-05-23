# @verolas/api

Verolas API gateway. FastAPI on Python 3.12, OIDC token verification against Keycloak, RLS scoped Postgres access, Prometheus metrics, SLA tier instrumentation per the bible's four tier model.

## Status

Skeleton. The HTTP layer, middleware, auth dependency, SLA tier instrumentation, Prometheus exposition, structured logging, OpenAPI docs, and Pydantic API schemas are all in place. Database wiring lands in the next workstream; v1 routes return 501 until then.

## Local setup

```bash
cd apps/api
uv sync
uv run pytest
uv run uvicorn verolas_api.main:app --reload
```

Then visit `http://localhost:8000/docs` for the auto generated OpenAPI UI.

## Configuration

Settings load from `VEROLAS_API_*` environment variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `VEROLAS_API_ENVIRONMENT` | `dev` | dev / staging / prod |
| `VEROLAS_API_LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR / CRITICAL |
| `VEROLAS_API_LOG_JSON` | `true` | JSON logs everywhere except dev consoles |
| `VEROLAS_API_OIDC_ISSUER` | `http://localhost:8080/realms/verolas` | Keycloak issuer URL |
| `VEROLAS_API_OIDC_AUDIENCE` | `verolas-api` | Expected `aud` claim |
| `VEROLAS_API_OIDC_JWKS_CACHE_TTL_SECONDS` | `600` | JWKS cache lifetime |
| `VEROLAS_API_DATABASE_URL` | unset | Postgres URL, used once DB wiring lands |

## Endpoints

| Path | Auth | SLA tier | Purpose |
| --- | --- | --- | --- |
| `GET /healthz` | none | Tier 1 | Liveness probe |
| `GET /readyz` | none | Tier 1 | Readiness probe |
| `GET /metrics` | none | Tier 1 | Prometheus exposition |
| `GET /docs` | none | n/a | Swagger UI |
| `GET /openapi.json` | none | n/a | OpenAPI spec |
| `GET /v1/users/me` | bearer | Tier 1 | Current user (501 until DB) |
| `GET /v1/organizations/` | bearer | Tier 1 | Org list (501 until DB) |
| `GET /v1/projects/` | bearer | Tier 1 | Project list (501 until DB) |

## SLA tiers

Each endpoint declares its tier with `@sla_tier(N)`. The middleware records latency into `verolas_request_duration_seconds`, labelled by tier, route, method, status. Tier ceilings from the bible:

- Tier 1: p95 under 30 seconds (interactive)
- Tier 2: p95 under 5 minutes (heavy interactive)
- Tier 3: p95 under 30 minutes (deliverable)
- Tier 4: p95 under 60 minutes (long compute)

Requests exceeding their ceiling increment `verolas_sla_violations_total` and log a structured warning. Alerting wires onto these signals in observability work.

## Structured logging

structlog with JSON output in non dev environments. Every log line inside a request carries the `request_id` from the `X-Request-ID` header (echoed back on response).

## Image

The image workflow at `.github/workflows/image.yml` builds this Dockerfile, scans with Trivy, signs with Cosign keyless, and pushes to `ghcr.io/verolas/api`.

## Tests

```
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest
```

All four are green on commit.
