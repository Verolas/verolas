# ADR 003: CI/CD foundation, GitHub Actions, image pipeline, self hosted runners ready

- Status: accepted
- Date: 2026-05-23
- Deciders: Shramish Kafle (founder, CEO)
- Consulted: ADR 001, ADR 002
- Informed: founding team

## Context

The repo needs CI to catch regressions on every change, an image pipeline that builds, scans, and signs every container we ship, secrets scanning, and a pre commit harness that mirrors CI so contributors get the same signal locally. The Verolas stack baseline calls for GitHub Actions with self hosted runners on Hetzner. The pragmatic order of operations is: get every workflow in place today on GitHub hosted runners, scaffold self hosted runners so the cluster install is a single Helm command, and switch the runs-on label per workflow when the cluster has the headroom to absorb the load.

## Options considered

### Option A: Stand up the complete pipeline today on GitHub hosted runners, scaffold self hosted runners, no live image yet (chosen)

- Pros: every CI/CD bullet from the stack baseline has a corresponding workflow in `.github/workflows/` today. Workflows that depend on artefacts which do not yet exist (Dockerfiles, Python projects, Rust crates, Playwright config) discover dynamically and skip gracefully, so adding the first Dockerfile or pyproject.toml lights up the pipeline with no further workflow changes. Self hosted runners are one helm install away when the cluster grows.
- Cons: no real image build runs yet because there are no Dockerfiles. The IaC plan workflow waits on org level GitHub Actions secrets that the operator must add.
- Cost: zero direct cost today. GitHub free minutes cover the placeholder runs comfortably.
- Reversibility: trivial.

### Option B: Wait for product code to exist before adding the image, test, and plan workflows

- Pros: nothing speculative ships.
- Cons: every workflow ends up rushed and merged at the same time as the first real feature. Failure modes show up in the wrong PR. The team has to invent the rules at the moment they break.
- Cost: opportunity cost.
- Reversibility: not really an issue, just slower.

### Option C: Install self hosted runners today on the dev cluster

- Pros: matches the stack baseline literally.
- Cons: the dev cluster is one CX23 with roughly 2.5 GB free after the cluster system services. The ARC controller plus one runner pod consumes most of that, leaving no headroom for product workloads. The dev cluster cannot host both runners and the work the runners would build.
- Cost: cluster sizing pressure earlier than needed.
- Reversibility: reversible, but wasted effort right now.

## Decision

Adopt Option A.

CI on GitHub hosted Ubuntu 24.04 runners covers six workflows that match the stack baseline bullet for bullet:

| Bullet | Workflow | Today's behaviour |
| --- | --- | --- |
| Lint, typecheck, test (Node) | `ci.yml` | Active. Runs `pnpm lint`, `pnpm typecheck`, `pnpm test` plus prose dash check and gitleaks. |
| Test runners (Python) | `test-python.yml` | Skips when no `pyproject.toml` exists. Activates when the first Python project lands. |
| Test runners (Rust) | `test-rust.yml` | Skips when no `Cargo.toml` exists. Activates when the first crate lands. |
| Test runners (E2E) | `test-e2e.yml` | Skips when `apps/web/playwright.config.*` is absent. Activates with the first Playwright config. |
| Build pipelines, container scanning, image signing | `image.yml` | Discovers Dockerfiles in `apps/*` and `services/*`, builds with Buildx, pushes to `ghcr.io`, scans with Trivy, signs with Cosign keyless via Sigstore OIDC. Skips when no Dockerfiles. |
| IaC plan on PR | `iac-plan.yml` | Runs `tofu plan` per affected environment and posts the plan as a sticky PR comment. Skips environments that have no `.tf` files yet. Requires org secrets. |
| IaC validate | `iac.yml` | Runs `tofu fmt -check` and `tofu validate` per environment that has `.tf` files. Active for `dev`, skips `staging` and `prod` for now. |
| PR title, no phase | `pr-meta.yml` | Active. Conventional Commits on PR title, hard fail on numbered build step mentions. |
| Pre commit hooks | `.pre-commit-config.yaml` | Active. Trailing whitespace, EOF fixer, YAML and JSON validation, gitleaks, tofu fmt, commitlint on commit messages, plus the shared prose and no phase scripts. |

Self hosted runners are scaffolded under `infra/helm/actions-runner-controller/` with a controller chart, a runner scale set chart, and a README that explains the install order and the GitHub App credential setup. The install is gated on cluster headroom. When self hosted runners go live, the migration is a `runs-on: verolas-runners` change per workflow.

The image workflow signs with Cosign keyless using the GitHub Actions OIDC token, no key material to manage. Trivy is configured to fail on `CRITICAL` and `HIGH` severities for fixed vulnerabilities, with the SARIF report uploaded to GitHub code scanning so vulnerabilities show up on the security tab.

## Consequences

Positive:

- Every CI/CD baseline bullet has a working workflow today.
- Adding a Dockerfile, a Python project, a Rust crate, or a Playwright config lights up the matching workflow with no extra plumbing.
- Trivy and Cosign sit on the same matrix as the build, so we cannot push an unscanned or unsigned image even by mistake.
- Cosign keyless means there is no signing private key to rotate or lose.
- IaC plan on PR makes infra changes self documenting. Reviewers see the exact resource diff in the PR thread before merge.
- Pre commit catches everything CI catches, locally and faster, including the commit message format on the commit hook stage.

Negative:

- The IaC plan workflow waits on the operator to add org level GitHub Actions secrets (see `.github/SECRETS.md`). Without those, the workflow runs but exits before plan.
- Image, Python, Rust, E2E workflows are dormant until their first target lands. They cost nothing while dormant. They produce no signal either.
- Self hosted runners are not installed today. The first real image build runs on GitHub hosted minutes, which are free at our scale but finite over time.

New work created:

- Operator adds the GitHub Actions secrets listed in `.github/SECRETS.md` for the IaC plan workflow to function.
- Install ARC on the cluster once headroom exists, then flip CI workflows to `runs-on: verolas-runners` one at a time.
- When the first Dockerfile lands, watch the image workflow on the same PR; tune Trivy severity threshold or ignore rules if the base image surfaces noise.

## Compliance and audit notes

- Cosign keyless via Sigstore produces a transparency log entry per signature. The signature plus log entry are independently auditable. This satisfies the EU AI Act high risk record keeping posture for software provenance.
- Trivy SARIF uploads to GitHub code scanning give us a tamper resistant vulnerability history per image.
- gitleaks runs on every PR and on every local commit. Secrets that escape past gitleaks are rotated, not redacted in place.
- CODEOWNERS gives the founder approval on every change today. The file will partition by area as the team grows.

## Follow ups

1. Add org level GitHub Actions secrets per `.github/SECRETS.md` so the IaC plan workflow runs end to end.
2. Install ARC on the cluster once the cluster is scaled up or a dedicated runner machine is provisioned.
3. Migrate CI workflows from `ubuntu-24.04` to `verolas-runners` one at a time once ARC is live.
4. Add a release workflow that promotes signed images from `latest` to a versioned tag on each release tag push.

## References

- GitHub Actions: https://docs.github.com/actions
- gitleaks: https://github.com/gitleaks/gitleaks
- pre commit: https://pre-commit.com
- OpenTofu setup action: https://github.com/opentofu/setup-opentofu
- Conventional Commits: https://www.conventionalcommits.org
- Trivy action: https://github.com/aquasecurity/trivy-action
- Cosign keyless signing: https://docs.sigstore.dev/cosign/signing/overview
- actions-runner-controller: https://github.com/actions/actions-runner-controller
- Related: [[ADR 001]], [[ADR 002]]
