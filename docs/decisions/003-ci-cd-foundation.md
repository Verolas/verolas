# ADR 003: CI/CD foundation, GitHub Actions on hosted runners, pre commit hooks, deferred image pipeline

- Status: accepted
- Date: 2026-05-23
- Deciders: Shramish Kafle (founder, CEO)
- Consulted: ADR 001, ADR 002
- Informed: founding team

## Context

The repo needs CI to catch obvious regressions on every change, plus a basic pre commit harness so contributors do not push obvious issues. The Verolas stack baseline (Part 9) names GitHub Actions with self hosted runners on Hetzner as the long term destination. Two facts shape the trade off today:

1. There is no product code yet. Lint, typecheck, and test scripts are placeholders that echo. Container images do not exist yet because services do not exist yet. Image scanning and signing pipelines are not actionable.
2. The dev cluster is a single CX23 with 4 GB of RAM. Running self hosted GitHub Actions runners on that cluster would compete with whatever product workloads we run there. Self hosted runners are revisited once there is a real, larger cluster and an actual build to run.

The right move now is to ship a small, honest CI that catches what is genuinely catchable today, plus the hooks and templates that the team will lean on later.

## Options considered

### Option A: GitHub hosted runners, lint and IaC validate, pre commit harness, defer image and self hosted (chosen)

- Pros: zero new infra cost (GitHub free minutes cover us at this stage), pre commit catches issues before push, IaC formatting and validation enforced on every PR, conventional commits and the prose dash and no phase rules enforced at PR time.
- Cons: no real test signal yet because the codebase is mostly placeholders. Self hosted runners and image pipelines are deferred.
- Cost: zero direct cost.
- Reversibility: trivial. Adding self hosted runners or image build jobs is a matter of new workflow files.

### Option B: Stand up self hosted GitHub Actions runners on the dev cluster now

- Pros: matches the stack baseline literally, exercises the cluster.
- Cons: the cluster cannot host runners and product workloads on 4 GB. Premature optimisation against a target that does not exist yet.
- Cost: cluster sizing pressure earlier than needed.
- Reversibility: reversible but wasted effort.

### Option C: Wait, do nothing until there is real code

- Pros: no work.
- Cons: prose dash rule, no phase rule, conventional commits rule, IaC fmt and validate, secret scanning, are all things we want enforced today. A PR that violates them lands quietly without CI.
- Cost: opportunity cost of regressions slipping in.
- Reversibility: easy but unhelpful.

## Decision

Adopt Option A.

Three workflows go live on GitHub hosted Ubuntu 24.04 runners:

1. `.github/workflows/ci.yml` workspace lint, typecheck, test, prose dash check, no phase check, gitleaks. Runs on every PR and push to main.
2. `.github/workflows/iac.yml` tofu fmt and validate for every populated `infra/live/<env>` directory. Triggered by PRs that touch `infra/**`.
3. `.github/workflows/pr-meta.yml` conventional commits on PR title and a custom check that no PR title or body mentions `phase N`.

Plus the supporting harness:

- `.pre-commit-config.yaml` runs trailing whitespace, end of file fixer, YAML and JSON validation, gitleaks, tofu_fmt, and the two custom scripts locally before every commit.
- `scripts/check-prose-dashes.sh` and `scripts/check-no-phase.sh` are shared by the CI workflows and pre commit, so behaviour is identical local and remote.
- `.gitleaks.toml` allowlists the tfvars example file and the ADR text from secret scanning false positives.
- `.editorconfig` standardises whitespace handling across editors.
- `.github/pull_request_template.md` and `.github/CODEOWNERS` shape the PR workflow.

## Consequences

Positive:

- Every PR is checked for the rules we actually care about today: secrets, prose dashes, phase mentions, IaC formatting.
- Local pre commit gives a fast feedback loop that mirrors CI exactly.
- The CI pipeline can grow into self hosted runners and image build jobs with new workflow files; nothing about today's choices blocks that path.

Negative:

- Test and typecheck signals are weak today because the codebase is largely placeholders. Real signal arrives as the apps and packages fill in.
- The IaC plan step does not run in CI yet. Plan needs Hetzner and Cloudflare credentials as GitHub Actions secrets, plus an SSH key for kube hetzner's `file()` calls at plan time. Adding plan on PR is a small follow up once the operator decides which secrets to push to the org level secret store.

New work created:

- Configure org level GitHub Actions secrets (Hetzner token, Cloudflare token, Hetzner S3 access key and secret) before adding a tofu plan on PR job.
- Migrate to self hosted runners once the cluster can host them without competing with product workloads.
- Add container image build, scan, and sign workflows when the first deployable image lands.

## Compliance and audit notes

- gitleaks runs on every PR and on every commit locally. Secrets that escape past gitleaks are rotated, not redacted in place.
- CODEOWNERS gives the founder approval on every change today. As the team grows, the file will partition ownership by area (apps, infra, packages, agents, prompts, evals).
- PR template requires the change to call out engineering calculation or prompt changes, so reviewers know when to ask for an eval delta. This matches the EU AI Act high risk record keeping posture from ADR 002.

## Follow ups

1. Add a `tofu plan` job on PRs touching `infra/**`, once GitHub Actions secrets are configured.
2. Stand up self hosted runners on Hetzner once the cluster grows.
3. Add Docker image build, Trivy scan, Cosign sign workflows when the first deployable service is ready.
4. Wire commitlint into pre commit so the conventional commits rule runs on every local commit, not only on PR title at GitHub.

## References

- GitHub Actions hosted runners: https://docs.github.com/actions/using-github-hosted-runners/about-github-hosted-runners
- gitleaks: https://github.com/gitleaks/gitleaks
- pre commit: https://pre-commit.com
- OpenTofu setup action: https://github.com/opentofu/setup-opentofu
- Conventional Commits: https://www.conventionalcommits.org
- Related: [[ADR 001]], [[ADR 002]]
