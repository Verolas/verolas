# verolas-web Kubernetes manifests

Deployment, Service, Traefik Middleware (security headers + CSP), and IngressRoute for the Verolas web app.

## Apply

```bash
export KUBECONFIG=~/.kube/verolas-dev.yaml

kubectl apply -f infra/k8s/web/namespace.yaml
kubectl apply -f infra/k8s/web/deployment.yaml
kubectl apply -f infra/k8s/web/ingressroute.yaml
```

The Deployment references `ghcr.io/verolas/web:latest`. The image workflow builds and signs the image on every push to main. Override the tag for pinned rollouts via kubectl edit or kustomize.

## CSP

The default Content Security Policy is conservative: `default-src 'self'`, no `frame-ancestors`, no remote scripts beyond `'self'`. The Next.js client uses `'unsafe-inline'` for the styles emitted by the Tailwind CSS variables and for the inline script needed by React server components hydration. We tighten this with nonces once the production observability stack is in place.

## Health probes

`/login` is the readiness and liveness probe target. The page is always renderable and does not depend on any backend, so it returns 200 as long as the Next.js server is up.

## Cost notes

The web pod runs at 100m / 256Mi requests, 1 CPU / 512Mi limits. Single replica fits comfortably on the existing dev node.
