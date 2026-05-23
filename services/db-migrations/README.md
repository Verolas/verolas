# verolas-db-migrations

Alembic migration framework for the Verolas PostgreSQL schema. Sits in `services/` because it is a deployable artefact (Job that runs against the cluster), not a long lived service.

## Why a shared migration project

Multiple Python services (API gateway, agent runners, RAG ingest) will need access to the same schema. Putting Alembic in one project that depends on the shared SQLAlchemy models means only one source of truth for the schema, and migrations are run by exactly one CI job in exactly one order.

Today the SQLAlchemy models do not exist. The Alembic env.py is wired to read the database URL from `VEROLAS_DATABASE_URL`, ready for the first real revision the day the API workspace lands.

## Local setup

```bash
cd services/db-migrations
uv sync
uv run pytest
```

## Running migrations

Set the database URL once per shell:

```bash
export VEROLAS_DATABASE_URL="postgresql+psycopg://verolas_app:<password>@localhost:5432/verolas"
```

Common Alembic commands:

```bash
uv run alembic current                 # show current head
uv run alembic history                 # show migration graph
uv run alembic upgrade head            # apply outstanding migrations
uv run alembic downgrade -1            # roll back one step
uv run alembic revision -m "describe"  # author a new migration
```

## How migrations run in production

A Kubernetes Job runs the same `alembic upgrade head` command in the cluster, with `VEROLAS_DATABASE_URL` pointing at the in cluster Postgres service. The Job runs as a step of every release. Until that wiring exists, migrations are applied manually via `kubectl exec` against the operator's running pod or via a temporary port forward.

## Adding the first real migration

1. Add the SQLAlchemy models in the application workspace (likely `apps/api`).
2. Make `db_migrations` depend on the application's package so models import cleanly.
3. Set `target_metadata` in `alembic/env.py` to the imported `Base.metadata`.
4. Run `uv run alembic revision --autogenerate -m "initial schema"`.
5. Review the generated revision, commit, open PR.
