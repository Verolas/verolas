# live/dev

Composition for the Verolas dev environment.

## Topology

- Single Hetzner Cloud private network (`10.42.0.0/16`) in `eu-central`
- 3 control plane nodes (CCX13) and 3 worker nodes (CCX23) in Nuremberg (`nbg1`)
- k3s v1.31, Cilium CNI, Hetzner Cloud load balancer
- DNS records on the `verolas.com` zone:
  - `dev.verolas.com` to the cluster load balancer
  - `*.dev.verolas.com` wildcard CNAME for cluster services
  - Apex and `www` left disabled until the marketing site exists

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
5. Install in cluster services per `infra/helm/README.md`.

## Cost ballpark

At the time of writing, this dev topology runs approximately:

- 3 control plane CCX13: about 14 EUR per node per month
- 3 worker CCX23: about 26 EUR per node per month
- 1 load balancer (LB11): about 6 EUR per month
- Network and traffic: under 5 EUR per month at dev scale

Roughly 130 EUR per month for the dev cluster. Confirm against the current Hetzner pricing page before applying.

## Tear down

```bash
tofu destroy
```

Acceptable for dev. Never run in staging or prod without an explicit decision and a backup of state.
