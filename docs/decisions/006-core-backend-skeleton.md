# ADR 006: Core backend skeleton, FastAPI, structlog, Prometheus, SLA tiering, OIDC integration

- Status: accepted
- Date: 2026-05-23
- Deciders: Shramish Kafle (founder, CEO)
- Consulted: ADR 003, ADR 004, ADR 005
- Informed: founding team

## Context

The Verolas API gateway is the HTTP front door for every product workflow. The stack baseline calls for FastAPI plus Pydantic v2, versioned routes, a per request observability story, and Tier 1 to Tier 4 performance SLA instrumentation. The auth library from ADR 005 already provides the OIDC verifier and the tenant scoping primitive. The cluster from ADR 002 and the database from ADR 004 are in place. This ADR pins the choices that turn those primitives into a running service.

## Options considered

### Web framework: FastAPI (chosen)

- Pros: the bible mandates it. First class Pydantic v2 integration, async by default, automatic OpenAPI generation. Mature dependency injection model maps cleanly to per request auth and tenancy resolution.
- Cons: it is a microframework. We add structured logging, Prometheus, rate limiting, and SLA tiering ourselves, but each is small and explicit.

### Configuration: pydantic-settings with env prefix (chosen)

- Settings load from `VEROLAS_API_*` env vars. Type validated at startup, so a bad config fails fast instead of crashing on first use.

### Logging: structlog with JSON renderer outside dev (chosen)

- Stdlib logging bridged into structlog so library logs flow through the same pipeline.
- `RequestIdMiddleware` binds `request_id` into the contextvars before the request runs and clears it after. Every log inside a request carries the id, the `X-Request-ID` response header echoes it.
- JSON in staging and prod, pretty console in dev (toggled by `VEROLAS_API_LOG_JSON`).

### Metrics: prometheus_client with a fresh registry per app instance (chosen)

- Each `create_app` call builds its own `CollectorRegistry` so tests do not bleed metrics across cases.
- `verolas_request_duration_seconds` is a histogram labelled by tier, method, route, status, with buckets covering each tier ceiling.
- `verolas_requests_total` is the matching counter for rate calculations.
- `verolas_sla_violations_total` counts requests over the declared tier ceiling.

### SLA tiering: per route decorator plus middleware (chosen)

- Bible defines four tiers: 1 under 30 seconds, 2 under 5 minutes, 3 under 30 minutes, 4 under 60 minutes.
- The `@sla_tier(N)` decorator attaches the tier to the endpoint function. `SlaTierMiddleware` reads it off the matched route and records duration into the histogram with `tier` as a label. Over ceiling requests increment the violations counter and emit a structured warning.
- Routes without an explicit tier default to tier 1 in the middleware. Reviewing PRs against a checklist that requires a tier on every new route is the discipline that keeps the default rare.

### Auth integration: bearer token verified via `services/auth`, dependency injected (chosen)

- `require_auth` returns the parsed `TokenClaims`. `require_role(role)` builds a dependency that enforces the caller carries at least the given role.
- `CurrentAuth = Annotated[AuthContext, Depends(require_auth)]` lets routes write `auth: CurrentAuth` without triggering the `B008` lint rule and without the legacy `arg = Depends(...)` shape.

### OpenAPI: built in FastAPI generation (chosen)

- The schema is exposed at `/openapi.json`. The Swagger UI at `/docs` is enabled in every environment for now. Once we have a public API for customer integrations, the docs URL is gated behind auth and a published spec lives separately.

### Rate limiting: Traefik middleware at ingress (chosen)

- We do not implement rate limiting in the app. Traefik already terminates ingress and the `RateLimit` middleware does it accurately and uniformly across all routes.
- Default policy: 60 requests per minute average, 120 burst, per source IP. Tightened per tier later if needed.

### Container shape: distroless principles on python:3.12-slim (chosen)

- Multi stage build. Builder uses uv to install dependencies into a venv. Runtime is python:3.12-slim with tini as PID 1, runs as `uid 1001` non root, drops all capabilities, read only root filesystem at deploy time, seccomp `RuntimeDefault`.
- Image is built and signed by the image workflow on every push to main.

## Decision

Adopt the chosen options. Concretely:

| Bible bullet | Implementation |
| --- | --- |
| FastAPI app structure with versioned `/v1` routes | `apps/api/verolas_api/main.py` `create_app`, `routes/v1/__init__.py` `api_v1` router |
| Pydantic models for User, Organization, Project | `apps/api/verolas_api/schemas/{user,organization,project}.py` matching Postgres enums and Keycloak realm roles |
| API gateway (Traefik) with rate limiting | `infra/k8s/api/ingressroute.yaml` Traefik IngressRoute plus RateLimit and security headers Middlewares |
| Healthcheck, metrics, structured logging baseline | `/healthz`, `/readyz`, `/metrics` plus structlog with JSON in non dev, request ID middleware |
| OpenAPI generation working | FastAPI default at `/openapi.json` and `/docs` |
| Performance SLA targets defined and instrumented | `@sla_tier(N)` decorator + `SlaTierMiddleware` recording per tier histograms, violation counters, and structured warnings |

## Consequences

Positive:

- Every endpoint inherits the right observability and security posture for free. The pattern for adding a new route is a four line decorator block plus the handler body.
- The SLA tiering is metric driven, not aspirational. Dashboards and alerts wire directly onto `verolas_request_duration_seconds` and `verolas_sla_violations_total`.
- The auth library does the heavy lifting; the API layer is a thin dependency injection layer over it.

Negative:

- The Deployment manifest references `ghcr.io/verolas/api:latest`. Tag pinning to a commit SHA is mandatory before any prod rollout. The image workflow already produces digest pinned tags; the deployment is updated by the release process to consume them.
- Database access is not wired yet. v1 routes return 501 until the next workstream lands the `psycopg` connection pool, the `sql_set_tenancy` call site, and the actual queries.

New work created:

- Wire psycopg connection pool plus a FastAPI dependency that opens a transaction, sets tenancy, hands the connection to the handler, commits or rolls back.
- Add the cluster's Postgres URL to a Kubernetes Secret named `verolas-api-db`, mounted by the Deployment.
- Add the API to the IngressRoute hostname list for staging and prod when those clusters come online.
- Replace `latest` with a SHA pinned tag in the Deployment when rollout discipline tightens.
- Add WebAuthn step up for sensitive operations once apps/web exists.

## Compliance and audit notes

- Every request carries a `X-Request-ID`. The structured logs and metrics use the same id, so an audit reviewer can pull every log line for a given request from a single field.
- SLA violations land in both metrics and logs, so the audit trail for performance against the bible's tier model is independently reproducible.
- The Traefik security headers middleware sets HSTS, no sniff, frame deny, referrer policy. Matches the OWASP secure headers baseline.

## Follow ups

1. Wire psycopg async connection pool, build the FastAPI dependency that opens a transaction and calls `sql_set_tenancy`, replace the 501s on v1 routes with real implementations.
2. Add a smoke test workflow that boots the image in CI, hits `/healthz` and `/readyz`, validates a Prometheus scrape, and asserts the OpenAPI schema is valid JSON.
3. Add ADR 007 for the WebAuthn step up flow once the frontend is in place.

## References

- FastAPI: https://fastapi.tiangolo.com
- Pydantic v2: https://docs.pydantic.dev
- structlog: https://www.structlog.org
- prometheus_client: https://github.com/prometheus/client_python
- Traefik RateLimit middleware: https://doc.traefik.io/traefik/middlewares/http/ratelimit/
- Related: [[ADR 003]], [[ADR 004]], [[ADR 005]]
