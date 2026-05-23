# PostgreSQL cluster (CloudNativePG)

Cluster and backup manifests for the Verolas Postgres database. Apply order matters because the operator must exist before the Cluster CR is accepted, and the backup secret must exist before the Cluster comes up if backup is enabled.

## Prereqs

- CloudNativePG operator is installed. See `infra/helm/cnpg-operator/README.md`.
- The custom `postgres-pgvector` image is built and tagged at the version referenced in `cluster-dev.yaml`. The image workflow at `.github/workflows/image.yml` handles this once `services/postgres-pgvector/Dockerfile` lands on `main`.
- A Hetzner Object Storage bucket exists for the backup destination. For dev: `verolas-pgbackup-dev` in `nbg1`. For prod: `verolas-pgbackup-prod` in `fsn1`. Versioning enabled. Object Lock disabled. Private visibility.
- Hetzner Object Storage credentials scoped only to the backup bucket are generated and ready to apply as a Kubernetes secret.

## Install order

```bash
export KUBECONFIG=~/.kube/verolas-dev.yaml

# 1. Namespace
kubectl create namespace postgres

# 2. Backup credentials secret (never commit real values)
kubectl -n postgres create secret generic postgres-backup-credentials \
  --from-literal=ACCESS_KEY_ID="<access-key-id>" \
  --from-literal=ACCESS_SECRET_KEY="<secret-key>"

# 3. Cluster
kubectl apply -f infra/k8s/postgres/cluster-dev.yaml

# 4. Scheduled backup
kubectl apply -f infra/k8s/postgres/scheduledbackup.yaml
```

Watch the cluster come up:

```bash
kubectl -n postgres get clusters,pods -w
```

Expect roughly three minutes from `kubectl apply` to a ready instance. The operator pulls the image, runs `initdb`, applies the `postInitTemplateSQL` snippets that install `vector`, `pg_stat_statements`, and `pgcrypto`, then takes the first base backup.

## Verify pgvector

```bash
kubectl -n postgres exec -it verolas-pg-1 -- psql -U postgres -d verolas \
  -c "SELECT extname, extversion FROM pg_extension ORDER BY extname;"
```

Expect a row for `vector`.

## Take a manual backup

```bash
kubectl apply -f - <<'YAML'
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata:
  name: verolas-pg-manual-$(date +%Y%m%d-%H%M)
  namespace: postgres
spec:
  cluster:
    name: verolas-pg
YAML
```

## Restore (point in time)

To restore to a specific moment in time, create a new Cluster with a `bootstrap.recovery` block that references the backup and a target time. Example:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: verolas-pg-restored
  namespace: postgres
spec:
  instances: 1
  imageName: ghcr.io/verolas/postgres-pgvector:latest
  bootstrap:
    recovery:
      source: verolas-pg
      recoveryTarget:
        targetTime: "2026-05-23 14:30:00.00000+00"
  externalClusters:
    - name: verolas-pg
      barmanObjectStore:
        destinationPath: s3://verolas-pgbackup-dev/verolas-pg
        endpointURL: https://nbg1.your-objectstorage.com
        s3Credentials:
          accessKeyId:
            name: postgres-backup-credentials
            key: ACCESS_KEY_ID
          secretAccessKey:
            name: postgres-backup-credentials
            key: ACCESS_SECRET_KEY
```

This restores into a parallel `verolas-pg-restored` cluster. Once verified, promote it or copy the data back.

## Verify PITR end to end

Quarterly we run the following test:

1. Write a known row into a `pitr_test` table with the current timestamp.
2. Wait one minute (so WAL captures the write).
3. Note the timestamp.
4. Drop the row.
5. Restore into a `verolas-pg-pitr` cluster targeting the noted timestamp.
6. Confirm the row exists in the restored cluster.
7. Delete the restored cluster.

This procedure is run on dev and staging. Prod is exercised in shadow mode against the staging clone.

## Cost notes

The dev cluster on a CX23 with one Postgres instance, 20Gi data volume, 10Gi WAL volume runs roughly:

| Item | Monthly net |
| --- | --- |
| Postgres pod resource share of the CX23 | included in node cost |
| 20Gi data volume | 0.80 EUR |
| 10Gi WAL volume | 0.40 EUR |
| Backup bucket usage at this scale | under 1 EUR |
| Total marginal cost | roughly 2 EUR |

Production scales linearly with data volume and instance count.
