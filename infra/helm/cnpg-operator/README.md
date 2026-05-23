# CloudNativePG operator

The operator that runs PostgreSQL clusters as Kubernetes custom resources. We install it once cluster wide. The actual Postgres cluster lives at `infra/k8s/postgres/`.

## Install

```bash
export KUBECONFIG=~/.kube/verolas-dev.yaml

helm repo add cnpg https://cloudnative-pg.github.io/charts
helm repo update

kubectl create namespace cnpg-system

helm install cnpg \
  --namespace cnpg-system \
  --version 0.23.0 \
  -f infra/helm/cnpg-operator/values.yaml \
  cnpg/cloudnative-pg
```

Verify the operator is ready:

```bash
kubectl -n cnpg-system get pods
kubectl -n cnpg-system get crd | grep cnpg.io
```

You should see at least these CRDs: `backups.postgresql.cnpg.io`, `clusters.postgresql.cnpg.io`, `pooler.postgresql.cnpg.io`, `scheduledbackups.postgresql.cnpg.io`, `objectstores.barmancloud.cnpg.io`.

## Why CloudNativePG

The operator is the production grade way to run PostgreSQL on Kubernetes. It handles:

- Synchronous and asynchronous streaming replication
- Automatic failover with promotion and replication slot management
- Online backups via Barman Cloud (pgBackRest workflow inside the cluster)
- Point in time recovery from object storage
- Rolling upgrades with zero downtime
- Affinity rules that keep replicas on separate nodes when the cluster has them

Alternatives we did not pick:

- Zalando postgres operator: older, larger surface, not as actively developed.
- Crunchy Postgres for Kubernetes: closed source for the operator binary in some tiers.
- Plain StatefulSet plus manual backups: too much operational burden for the founding team.

## Upgrade path

The operator follows semantic versioning. Patch and minor upgrades are safe via `helm upgrade`. Major upgrades read the operator release notes; the Postgres clusters keep running through operator upgrades because the data plane is decoupled.
