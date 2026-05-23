# live/dev

Composition for the Verolas dev environment.

## Topology

Single node k3s for early product development. This is intentionally small. Scale up when a pilot or HA testing requires it.

- 1 Hetzner Cloud CX22 (2 vCPU, 4 GB RAM, 40 GB SSD) in Nuremberg (`nbg1`)
- k3s v1.31, Cilium CNI, control plane untainted so workloads run on it
- No Hetzner load balancer (cost saving); cluster is reachable via kubectl port-forward, SSH tunnel, or Cloudflare Tunnel when that lands
- DNS records on the `verolas.com` zone:
  - `dev.verolas.com` not created yet (no LB target)
  - CAA record present so future Let's Encrypt certs work

## Cost ballpark

Approximate monthly net cost (Hetzner price page is the source of truth):

| Item | Qty | Monthly |
| --- | --- | --- |
| CX22 single node | 1 | 4.51 EUR |
| Persistent volumes (50 GB) | | 2.00 EUR |
| Object Storage state bucket | 1 | 5.99 EUR |
| Private network | | 0.00 EUR |
| Traffic (20 TB included) | | 0.00 EUR |
| **Subtotal net** | | **~13 EUR** |
| With 19% German VAT | | ~15 EUR |

If your company has a registered VAT ID, Hetzner reverse charges and you pay the net price.

## What does and does not run on this cluster

The CX22 has 4 GB RAM. That comfortably runs k3s plus a small set of application services for development, but not the full prod stack.

Fine to run today:

- One Postgres instance for development data
- One Redis
- Application services from `apps/api`, `apps/web` once they land
- cert-manager (small footprint, useful even on dev)
- Traefik (only if you want HTTP routing inside the cluster)

Defer until staging or prod (do not install on this dev node):

- HashiCorp Vault HA, Harbor, Linkerd. These are scaffolded under `infra/helm/` for when staging arrives.

## Apply

1. Complete `infra/PREFLIGHT.md`.
2. Copy `terraform.tfvars.example` to `terraform.tfvars` and fill it.
3. From this directory:
   ```bash
   tofu init -backend-config="access_key=$(grep hetzner_s3_access_key terraform.tfvars | cut -d'\"' -f2)" \
             -backend-config="secret_key=$(grep hetzner_s3_secret_key terraform.tfvars | cut -d'\"' -f2)"
   tofu plan -out=tfplan
   tofu apply tfplan
   ```
4. Capture the kubeconfig:
   ```bash
   tofu output -raw kubeconfig > ~/.kube/verolas-dev.yaml
   chmod 600 ~/.kube/verolas-dev.yaml
   export KUBECONFIG=~/.kube/verolas-dev.yaml
   kubectl get nodes
   ```
   You should see one node, `Ready`, role `control-plane`.

## Scaling up later

When you need HA or more capacity, change `infra/live/dev/main.tf`:

```hcl
control_plane_count               = 3
control_plane_server_type         = "ccx13"
worker_count                      = 3
worker_server_type                = "ccx23"
allow_scheduling_on_control_plane = false
```

Then `tofu plan` will show the additional nodes joining. Expect roughly 140 EUR per month net at that shape.

## Tear down

```bash
tofu destroy
```

Acceptable for dev. Stops the billing.
