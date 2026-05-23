# In cluster services (Helm)

Each subdirectory holds a `values.yaml` for a service installed into the cluster after OpenTofu has brought the cluster up. Install order is fixed and matters.

## Install order

```bash
export KUBECONFIG=~/.kube/verolas-dev.yaml

# 1. cert-manager (no dependencies)
kubectl create namespace cert-manager
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.16.2 \
  -f infra/helm/cert-manager/values.yaml

# 2. Traefik ingress (depends on cert-manager for TLS)
kubectl create namespace traefik
helm repo add traefik https://traefik.github.io/charts
helm install traefik traefik/traefik \
  --namespace traefik \
  --version 32.1.1 \
  -f infra/helm/traefik/values.yaml

# 3. Linkerd CRDs then control plane
helm repo add linkerd-edge https://helm.linkerd.io/edge
helm install linkerd-crds linkerd-edge/linkerd-crds \
  --namespace linkerd \
  --create-namespace
helm install linkerd-control-plane linkerd-edge/linkerd-control-plane \
  --namespace linkerd \
  --set-file identityTrustAnchorsPEM=ca.crt \
  --set-file identity.issuer.tls.crtPEM=issuer.crt \
  --set-file identity.issuer.tls.keyPEM=issuer.key \
  -f infra/helm/linkerd/values.yaml

# 4. Vault (independent, but bootstrap needs careful unseal)
kubectl create namespace vault
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault \
  --namespace vault \
  --version 0.30.0 \
  -f infra/helm/vault/values.yaml

# Init Vault once, copy unseal keys and root token to founder password manager
kubectl exec -n vault vault-0 -- vault operator init -key-shares=5 -key-threshold=3
# Unseal each replica three times with three of the five keys

# 5. Harbor (depends on cert-manager for registry TLS)
kubectl create namespace harbor
helm repo add harbor https://helm.goharbor.io
helm install harbor harbor/harbor \
  --namespace harbor \
  --version 1.16.0 \
  -f infra/helm/harbor/values.yaml
```

## Why not GitOps yet

This bootstrap is manual Helm on purpose. The Argo CD GitOps flow is added once the cluster has cert-manager and ingress working, since Argo itself wants TLS and a domain. Argo install lands in a follow up PR.

## Why values are stubs

The values files in this directory carry safe defaults plus comments at every spot that needs an environment specific override. Real domains, certificate authorities, and storage classes get filled in per environment once the cluster is up.
