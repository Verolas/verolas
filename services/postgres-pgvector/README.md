# postgres-pgvector

Custom PostgreSQL 17 image for Verolas with the `vector` extension pre installed.

## Why a custom image

CloudNativePG ships PostgreSQL images with the common extensions, but `pgvector` is not in the default set and is essential for our retrieval workloads. We extend the standard CNPG image so the cluster manifests can install the extension via a one line bootstrap.

## How it is built

The image workflow at `.github/workflows/image.yml` discovers this Dockerfile, builds it, scans with Trivy, signs with Cosign keyless, and pushes to `ghcr.io/verolas/postgres-pgvector`.

## How it is used

`infra/k8s/postgres/cluster-dev.yaml` sets:

```yaml
spec:
  imageName: ghcr.io/verolas/postgres-pgvector:latest
  bootstrap:
    initdb:
      postInitTemplateSQL:
        - CREATE EXTENSION IF NOT EXISTS vector;
```

The same applies to staging and prod with their respective image tags pinned to a specific commit SHA rather than `latest`.

## Versioning

The image tracks PostgreSQL 17 minor versions. When PG 17.x ships a security release, this Dockerfile gets bumped on the `FROM` line and the rebuild lands a new image. pgvector versions follow whatever is shipped by the Debian package for PG 17. For a specific pgvector version, switch to building from source in this Dockerfile.
