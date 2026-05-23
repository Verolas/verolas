# actions-runner-controller (ARC)

Self hosted GitHub Actions runners running on the Verolas Kubernetes cluster. Uses the newer official `gha-runner-scale-set` model, not the legacy summerwind controller.

## When to install

Not yet. The single node CX23 dev cluster has roughly 2.5 GB of free RAM after Cilium, Hetzner CCM, CSI, kured, and metrics server. The ARC controller plus one ephemeral runner pod would consume most of what is left, leaving no headroom for product workloads.

Install when at least one of the following is true:

- The dev cluster has been scaled up to 3 + 3 (HA) or larger.
- A dedicated small server (CX22 outside the cluster) is provisioned for runners.
- The cluster is reserved exclusively for CI and product workloads live elsewhere.

## How to install when the time comes

Two charts, in order. The controller installs once cluster wide. The runner scale set installs per group of runners.

### 1. Controller

```bash
export KUBECONFIG=~/.kube/verolas-dev.yaml
kubectl create namespace arc-systems

helm install arc \
  --namespace arc-systems \
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set-controller \
  --version 0.10.1 \
  -f infra/helm/actions-runner-controller/controller-values.yaml
```

### 2. GitHub authentication

A GitHub App is preferred over a personal access token. Create the App at the org or repo level with these permissions: Actions read, Administration read and write, Metadata read.

Capture the App ID, the installation ID, and the private key PEM. Store them as a Kubernetes secret:

```bash
kubectl create namespace arc-runners
kubectl -n arc-runners create secret generic arc-github-app \
  --from-literal=github_app_id=<APP_ID> \
  --from-literal=github_app_installation_id=<INSTALLATION_ID> \
  --from-file=github_app_private_key=arc-app-private-key.pem
```

### 3. Runner scale set

```bash
helm install verolas-runners \
  --namespace arc-runners \
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set \
  --version 0.10.1 \
  -f infra/helm/actions-runner-controller/runner-scale-set-values.yaml
```

After both charts are installed, every workflow that sets `runs-on: verolas-runners` will land on the cluster runners.

## How to switch CI to use these runners

Today's workflows use `runs-on: ubuntu-24.04` so they execute on GitHub hosted runners. After ARC is up, update workflows incrementally:

```yaml
jobs:
  example:
    runs-on: verolas-runners
```

Keep `ubuntu-24.04` as the fallback for any workflow that needs Linux specific tooling not yet baked into the runner container.

## How to monitor

```bash
kubectl -n arc-systems get pods
kubectl -n arc-runners get pods
kubectl -n arc-runners logs deploy/verolas-runners-listener
```

The listener pod connects to GitHub and spawns ephemeral runner pods when jobs queue.

## Cost note

ARC controller plus one idle listener costs the same as any other pod (negligible at our scale). Ephemeral runner pods consume resources only while jobs run. The real cost is the cluster size needed to host them.
