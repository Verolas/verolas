# Redis

Redis is used for ephemeral working state across the agent runtime, the LLM gateway cache, and any session or queue use case where Postgres would be overkill.

## Install on dev

```bash
export KUBECONFIG=~/.kube/verolas-dev.yaml

kubectl create namespace redis

# Auth secret. Generate a strong password from openssl, store the value in
# the founder password manager, and apply once.
kubectl -n redis create secret generic redis-auth \
  --from-literal=password="$(openssl rand -base64 32)"

helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

helm install redis \
  --namespace redis \
  --version 20.6.0 \
  -f infra/helm/redis/values-dev.yaml \
  bitnami/redis
```

Verify:

```bash
kubectl -n redis get pods
PASSWORD=$(kubectl -n redis get secret redis-auth -o jsonpath='{.data.password}' | base64 -d)
kubectl -n redis exec -it redis-master-0 -- redis-cli -a "$PASSWORD" PING
```

Expect `PONG`.

## Install on prod (future)

Same flow but apply `values-prod.yaml`. The chart accepts an in place upgrade from standalone to replication when the cluster has grown enough.

## Why Bitnami chart and not a Redis operator

The Bitnami chart is the most mature, widely deployed Redis chart, supports Sentinel out of the box, and integrates with the Hetzner CSI driver via standard StorageClass. A Redis operator (Spotahome, OT Container Kit) adds an extra moving part for a database we run as a cache, not as the source of truth. We may revisit if we need cluster sharding (Redis Cluster) at scale.

## Cost notes

Dev standalone with a 5 Gi PVC runs roughly:

| Item | Monthly net |
| --- | --- |
| Redis pod resource share of the CX23 | included in node cost |
| 5Gi data volume | 0.20 EUR |
| Total marginal cost | under 0.50 EUR |

Prod cluster scales with replica count and PVC size.
