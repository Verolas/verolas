# Verolas Infrastructure

All Verolas cloud infrastructure is defined as code in this directory. Nothing is provisioned by clicking in a console. Every cluster, network, DNS record, and certificate authority traces back to a file here.

## Layout

```
infra/
  README.md             this file
  PREFLIGHT.md          prerequisites before `tofu apply`
  .gitignore            keeps tfvars, state, and .terraform/ out of git
  live/                 environment compositions (call modules, pin versions)
    dev/                shared development cluster
    staging/            pre production cluster, mirrors prod topology
    prod/               production cluster, EU sovereign
  modules/              reusable modules, version pinned
    network/            Hetzner private network, subnets, firewalls
    k8s/                Kubernetes cluster bootstrap on Hetzner Cloud
    cloudflare-dns/     Cloudflare DNS records for the Verolas zones
    object-storage/     Hetzner Object Storage buckets
  helm/                 Helm values for in cluster services
    vault/              HashiCorp Vault for secrets
    harbor/             Harbor self hosted container registry
    cert-manager/       cert-manager for mTLS and ACME
    traefik/            ingress controller
    linkerd/            service mesh
```

## Tool of choice

We use **OpenTofu** (the open-source fork of Terraform), per `docs/decisions/001-monorepo-and-stack-baseline.md` and the broader stack baseline. Install:

```bash
brew install opentofu
tofu version
```

All examples in this directory use `tofu` rather than `terraform`. Both binaries are interchangeable at the CLI level for our HCL.

## State

State lives in Hetzner Object Storage with an S3 compatible API. Each environment has its own state bucket, configured in `live/<env>/backend.tf`. State is encrypted at rest by Hetzner and additionally encrypted client side via the `encrypt = true` backend option once we wire it.

## Workflow

1. Make changes in `modules/` or `live/<env>/`.
2. From `live/<env>/`, run `tofu init` once per environment, then `tofu plan`.
3. Review the plan. Never apply blind.
4. Open a PR with the plan output captured in the PR description.
5. Merge after review.
6. From `live/<env>/`, run `tofu apply` against the merged main. Apply is gated to a controlled runner once CI infrastructure is in place. Until then, the founder runs apply from a workstation with the production API token loaded.

## Secrets

API tokens never enter this repository. They live in:

- Local development: `infra/live/<env>/terraform.tfvars` (gitignored), exported as environment variables, or pulled from `op://` (1Password CLI) at apply time.
- CI and production: HashiCorp Vault, once Vault itself is up.

The chicken-and-egg between Vault and the rest of the stack is handled by bootstrapping Vault first with a single founder-held unseal key, then migrating to Shamir or auto unseal via Hetzner KMS when available.

## Where to start

Read `PREFLIGHT.md` next. It lists every account, token, and DNS step that must be completed before `tofu apply` can succeed.
