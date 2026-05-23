# verolas-api Kubernetes manifests

Deployment, Service, and Traefik IngressRoute for the API gateway. Applied after the cluster has cert manager and Traefik installed.

## Apply

```bash
export KUBECONFIG=~/.kube/verolas-dev.yaml

kubectl apply -f infra/k8s/api/namespace.yaml
kubectl apply -f infra/k8s/api/deployment.yaml
kubectl apply -f infra/k8s/api/ingressroute.yaml
```

The Deployment references `ghcr.io/verolas/api:latest`. The image workflow builds and signs this on every push to `main`. Override the image tag for a specific commit via kubectl edit or kustomize.

## Rate limiting

The `verolas-api-ratelimit` Traefik Middleware enforces 60 requests per minute average, 120 burst, per source IP. The IP strategy depth is 1, so it reads the first hop in `X-Forwarded-For` (Cloudflare).

Per environment overrides:
- dev: leave as is
- prod: tighten or loosen based on customer load profile, document the choice in the next ADR

## Health probes

- `livenessProbe` hits `/healthz`. The pod restarts if the probe fails three times.
- `readinessProbe` hits `/readyz`. The pod is removed from the Service endpoints when not ready, no restart.

Both probes are tier 1 endpoints and finish in milliseconds.

## Metrics scrape

The deployment carries Prometheus scrape annotations on the pod template. Prometheus discovers the pod via the annotation, scrapes `/metrics` every interval, and indexes the `verolas_*` metric families.

## Security posture

- Runs as `uid:gid 1001:1001`, non root, drops all Linux capabilities, read only root filesystem, seccomp `RuntimeDefault`.
- ServiceAccount token is not mounted; the app does not talk to the Kubernetes API.
- Image is pulled by digest in prod (override the deployment with a digest pinned tag on apply).

## Cost notes

The API pod request envelope is 100m CPU / 256 MiB. Limits are 1 CPU / 512 MiB. On the single CX23 dev node this is comfortable headroom.
