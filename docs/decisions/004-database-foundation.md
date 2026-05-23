# ADR 004: Database foundation, CloudNativePG, pgvector, Bitnami Redis, Alembic, S3 backups

- Status: accepted
- Date: 2026-05-23
- Deciders: Shramish Kafle (founder, CEO)
- Consulted: ADR 002, ADR 003
- Informed: founding team

## Context

Verolas needs durable storage for application state, ephemeral storage for working state and caches, and a versioned migration history for the relational schema. The stack baseline calls for PostgreSQL 17 with pgvector for embeddings, Redis for working state, pgBackRest style backups to Hetzner Storage Box, Alembic as the migration framework, and tested point in time recovery. This ADR turns each of those bullets into a concrete implementation that fits the current cluster while leaving a clean path to the production shape.

## Options considered

### Relational database: PostgreSQL via CloudNativePG (chosen)

- Pros: the operator manages streaming replication, automatic failover, continuous WAL archiving, point in time recovery, online backups via Barman Cloud, and rolling upgrades. The Cluster resource is the same shape on dev (1 instance) and prod (3 instance synchronous), so the prod cutover is a `kubectl apply` away.
- Cons: extra operator to keep upgraded. CRDs add cluster surface.
- Reversibility: hybrid. Moving off the operator is real work, but the data lives in standard Postgres so a logical or physical export is always possible.

Alternatives:

- Zalando postgres operator: older, larger surface, less actively developed.
- Crunchy Postgres for Kubernetes: closed source operator binary in some tiers.
- Plain StatefulSet plus manual backups: too much operational burden for the founding team.

### Vector extension: pgvector inside the same Postgres (chosen)

- Pros: single database, single backup path, transactions span structured and vector data. Avoids the operational cost of running a separate vector database for the first phase of the product.
- Cons: pgvector index performance trails dedicated vector stores at high QPS and high dimensionality. Acceptable through pilot scale, revisit when load demands it.
- Implementation: a custom container image (`services/postgres-pgvector/Dockerfile`) layers the official Debian package on top of the CloudNativePG PostgreSQL 17 image. The cluster bootstrap runs `CREATE EXTENSION vector` after `initdb`.

### Working state and cache: Bitnami Redis chart (chosen)

- Pros: most mature, most widely deployed Redis chart. Integrates with our Hetzner CSI driver via standard StorageClasses. Supports Sentinel for prod HA.
- Cons: not an operator; Sentinel topology changes require a chart upgrade rather than a CR edit.
- Implementation: standalone single replica on dev (`values-dev.yaml`), three replica Sentinel on prod (`values-prod.yaml`).

Alternatives considered: a Redis operator (Spotahome or OT Container Kit). Adds an extra moving part for a cache, not the source of truth. Revisit if Redis Cluster sharding becomes necessary.

### Backups: pgBackRest workflow via Barman Cloud to Hetzner S3 compatible Object Storage (chosen, with deviation)

- The stack baseline names `Hetzner Storage Box` as the offsite destination. Storage Box is SSH and SMB based, not S3, and CloudNativePG's Barman Cloud integration does not speak Storage Box. The modern equivalent on Hetzner is the S3 compatible Object Storage, encrypted at rest by Hetzner.
- Implementation: the `Cluster.spec.backup.barmanObjectStore` block points at a per environment bucket (`verolas-pgbackup-dev`, `verolas-pgbackup-prod`). Gzip plus AES256 client side encryption. 14 day retention on dev, 90 day on prod. A `ScheduledBackup` resource runs a full backup nightly at 02:00 UTC. WAL archiving runs continuously, so the recovery window is granular to the second.
- Rationale: same engineering intent as the stack baseline (durable offsite backup), better mechanics for our cluster.

### Migration framework: Alembic in a dedicated migration project (chosen)

- Pros: standard for SQLAlchemy projects, supports autogenerate when models exist, integrates cleanly with the Kubernetes Job pattern for release time migrations.
- Implementation: `services/db-migrations` is a Python project that contains the Alembic configuration and will hold the migration revisions. The `alembic/env.py` reads the connection string from `VEROLAS_DATABASE_URL` so the same project runs against dev, staging, and prod. Once the application's SQLAlchemy models exist in `apps/api`, the migration project depends on them and gains autogenerate.

### Point in time recovery: documented runbook plus quarterly validation (chosen)

- The `Cluster.bootstrap.recovery` block plus the `barmanObjectStore` external reference lets us restore into a parallel cluster at any target time inside the retention window. The runbook in `infra/k8s/postgres/README.md` describes the exact procedure.
- Quarterly we write a test row, take a backup, drop the row, restore to the target timestamp into a parallel cluster, and confirm the row is back. The procedure runs on dev and staging; prod is exercised in shadow mode against the staging clone.

## Decision

Adopt the chosen options. Concretely:

| Bullet | Implementation |
| --- | --- |
| CloudNativePG operator, PostgreSQL 17 cluster | `infra/helm/cnpg-operator` plus `infra/k8s/postgres/cluster-dev.yaml` (1 instance) and `cluster-prod.yaml` (3 instances synchronous) |
| pgvector extension | Custom image `services/postgres-pgvector/Dockerfile`, installed via `postInitTemplateSQL` |
| Redis cluster | Bitnami chart, `infra/helm/redis/values-dev.yaml` (standalone) and `values-prod.yaml` (Sentinel HA) |
| Backup strategy | Barman Cloud to Hetzner Object Storage with gzip plus AES256 encryption, daily scheduled backup, continuous WAL archiving. Hetzner Storage Box replaced by Object Storage as documented in the rationale. |
| Migration framework: Alembic | `services/db-migrations` Python project with `alembic.ini`, `alembic/env.py` reading `VEROLAS_DATABASE_URL`, ready for the first revision once application models land |
| Point in time recovery validated | Restore runbook and quarterly validation procedure in `infra/k8s/postgres/README.md` |

## Consequences

Positive:

- One operator and one database engine cover both structured and vector workloads. No second vector store to operate.
- Cluster definitions, backup config, and migrations all live in `infra/` and `services/`, fully reviewable as code.
- The dev to prod shape change is a parameter edit, not a redesign.
- Backups use the same Object Storage infrastructure as the Terraform state bucket, reusing operator knowledge.

Negative:

- The dev cluster on a single CX23 absorbs the operator, the Postgres pod, the Redis pod, and any application workload. Roughly 800 MB to 1 GB of RAM goes to data services before any app starts. Will not scale; this is acknowledged and the prod manifests live in the repo for when the cluster grows.
- pgvector performance at high dimensionality is bounded by Postgres's storage path. If retrieval QPS or vector count climbs into the millions, a dedicated vector store (Qdrant, scaffolded by ADR 002 but not yet sized) takes over. The relevant cutover is captured as a future ADR.

New work created:

- Build and push the `postgres-pgvector` image via the image workflow once this PR lands.
- Create the per environment Object Storage buckets for backups before applying the cluster manifests.
- Wire the application's SQLAlchemy models into `services/db-migrations` once `apps/api` exists.
- Add the K8s Job that runs `alembic upgrade head` on every release once a deployable application service exists.

## Compliance and audit notes

- All backups are encrypted client side with AES256 plus server side at rest by Hetzner. Encryption keys for the AES256 client side wrapper are derived from the backup bucket credentials and stored in the founder password vault. Rotation is a single secret update plus a Cluster restart.
- Retention windows match the EU AI Act high risk obligations for traceability of model and data versions: 14 days on dev for engineering debugging, 90 days on prod for audit and rollback.
- Point in time recovery is the primary safeguard against accidental schema or data destruction. Quarterly validation is the audit evidence that the backup chain works.

## Follow ups

1. Build and push `ghcr.io/verolas/postgres-pgvector:latest` via the image workflow.
2. Provision Object Storage buckets `verolas-pgbackup-dev` (nbg1) and `verolas-pgbackup-prod` (fsn1) before any apply.
3. Install the CNPG operator, then the dev Cluster, then the ScheduledBackup, in that order.
4. Run the first PITR validation within seven days of the cluster going live.
5. Track when the dev cluster needs to scale up to fit Postgres, Redis, and product workloads simultaneously.
6. Add Qdrant alongside Postgres if and when vector workload scale demands a dedicated store.

## References

- CloudNativePG: https://cloudnative-pg.io
- Barman Cloud: https://pgbarman.org
- pgvector: https://github.com/pgvector/pgvector
- Bitnami Redis chart: https://github.com/bitnami/charts/tree/main/bitnami/redis
- Alembic: https://alembic.sqlalchemy.org
- Hetzner Object Storage: https://www.hetzner.com/storage/object-storage
- Related: [[ADR 002]], [[ADR 003]]
