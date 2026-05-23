# ADR 002: Infrastructure baseline: Hetzner, kube-hetzner, OpenTofu, Cloudflare

- Status: accepted
- Date: 2026-05-23
- Deciders: Shramish Kafle (founder, CEO)
- Consulted: internal architecture notes, stack baseline (ADR 001)
- Informed: founding team

## Context

Verolas needs a sovereign EU hosted platform substrate for the entire build. The substrate must:

1. Sit inside the EU for data residency (GDPR plus the EU AI Act high risk regime).
2. Be reproducible end to end from source. No console clicks that the repo cannot reproduce.
3. Be cheap enough at the dev stage that an unfunded founder can run it indefinitely.
4. Scale cleanly to production volumes once customer pilots are in flight.
5. Keep state, secrets, and registry isolated from the founder workstation.

The bible (Part 9.7 and Part 9.8) calls Hetzner the primary, OpenTofu the IaC tool, Cloudflare the edge and DNS, Harbor the registry, and Vault the secrets store. This ADR locks in the specific implementations that realise that direction.

## Options considered

### Option A: Hetzner Cloud + kube-hetzner + OpenTofu + Cloudflare (chosen)

- Pros: Hetzner is EU sovereign, materially cheaper than the hyperscalers (factor of 3 to 5 at our sizes), and its API surface is small and reliable. kube-hetzner is the de facto open-source module for Hetzner Cloud Kubernetes, used in production by many shops. OpenTofu is the open fork of Terraform mandated by the bible. Cloudflare gives us global edge plus DNS with a single account.
- Cons: Hetzner has occasional capacity issues in specific node sizes. No managed Kubernetes; we bring our own. Limited managed data services compared to AWS or GCP. Cloudflare's WAF is good but its enterprise products are pricey at scale.
- Cost: at dev sizes, roughly 130 EUR per month for the full cluster. At staging, roughly 400 EUR per month. At prod entry size, roughly 1500 EUR per month, scaling with worker count.
- Reversibility: hybrid. The IaC abstractions in `infra/modules` give us a migration story to AWS or GCP if Hetzner fails us, but switching is real work, not a one liner.

### Option B: AWS EKS in eu-central-1

- Pros: managed control plane, mature ecosystem, every primitive is one service away. Enterprise customers expect AWS.
- Cons: roughly 3 to 5x our Hetzner cost at every size. Stronger lock in once IAM, KMS, and service primitives are wired. EU sovereignty story is muddier given the US owner.
- Cost: dev cluster alone runs roughly 400 to 600 EUR per month before any workloads. Production scales aggressively.
- Reversibility: hybrid. Lock in increases with each AWS managed service consumed.

### Option C: Bare metal Hetzner Robot from day one

- Pros: lowest unit cost at scale, full control.
- Cons: massive day one ops burden. No Hetzner Cloud Load Balancer integration. We are pre product market fit; bare metal day one is a distraction.
- Cost: lowest steady state, highest setup cost.
- Reversibility: hybrid. Moving from cloud to robot is straightforward; reverse is harder.

### Option D: OVHcloud or Scaleway managed Kubernetes

- Pros: also EU sovereign, managed control plane.
- Cons: less ecosystem maturity than Hetzner Cloud for our specific stack. Documentation thinner. Higher cost than Hetzner.
- Cost: similar to Hetzner Cloud, slightly higher.
- Reversibility: hybrid.

## Decision

Adopt Option A.

- Compute and network: Hetzner Cloud, EU central
- Kubernetes: kube-hetzner module, k3s distribution, 3 control plane plus 3 worker CCX nodes
- IaC: OpenTofu, S3 backend on Hetzner Object Storage
- Edge and DNS: Cloudflare
- Registry: Harbor self hosted
- Secrets: HashiCorp Vault self hosted, Raft storage, 3 replica HA
- Ingress: Traefik
- Mesh: Linkerd
- Certs: cert-manager with Let's Encrypt

Move to upstream Kubernetes (not k3s) before GA, captured as a future ADR.

## Consequences

Positive:

- One vendor for compute and network in the EU, with billing fully under our control.
- Cluster topology, DNS, certs, and registry all live in `infra/` and can be reviewed before any apply.
- The exit path is real: every module is portable in spirit; only the provider blocks change.

Negative:

- We own the cluster lifecycle. Patching, upgrades, etcd backups, capacity planning are our problem.
- Vault bootstrap involves a manual founder held unseal until we wire auto unseal via a KMS, which Hetzner does not yet provide natively.
- No managed Postgres, no managed Redis. CloudNativePG and Redis Operator give us self managed substitutes; this is acknowledged in the Part 9 stack and is on us to operate.

New work created:

- Provision the dev cluster from `infra/live/dev`.
- Wire CI to run `tofu plan` and post the diff on PRs.
- Add cluster autoscaler once the workload pattern is understood.
- Run prod readiness review before staging spins up.
- Migrate to upstream Kubernetes before GA.

## Compliance and audit notes

- Hetzner data centres in Falkenstein and Nuremberg are inside Germany. Data residency for personal data falls under GDPR with no transfer concern.
- Cloudflare is US owned. Per the GDPR Article 28 framework, customer personal data on Cloudflare is limited to the edge proxy path. The DPA with Cloudflare must be on file before prod customer traffic flows; this is a follow up before staging.
- Object Storage and cluster volumes are encrypted at rest by Hetzner. Customer specific encryption keys (CMK) are layered on top once the relevant workstream lands.
- Audit logging from the cluster (kube apiserver audit policy, Vault audit device) is required for the EU AI Act high risk record keeping obligation. The audit policy is added before any customer workload runs.

## Follow ups

1. Bring up the dev cluster, validate the smoke test in `infra/PREFLIGHT.md` step 7.
2. Sign the Cloudflare DPA before staging.
3. Add ADR 003 for kube apiserver audit policy and Vault audit device configuration.
4. Add ADR 004 for the k3s to upstream Kubernetes migration.
5. Build the staging composition.

## References

- kube-hetzner: https://github.com/kube-hetzner/terraform-hcloud-kube-hetzner
- OpenTofu: https://opentofu.org
- Hetzner Cloud: https://www.hetzner.com/cloud
- Hetzner Object Storage: https://www.hetzner.com/storage/object-storage
- Cloudflare: https://www.cloudflare.com
- Related: [[ADR 001]]
