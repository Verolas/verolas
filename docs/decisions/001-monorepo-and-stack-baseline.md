# ADR 001: Monorepo layout and stack baseline

- Status: accepted
- Date: 2026-05-23
- Deciders: Shramish Kafle (founder, CEO)
- Consulted: internal architecture notes
- Informed: founding team

## Context

The Verolas repository must be initialized as a Turborepo monorepo using pnpm workspaces, with top level directories `apps/web`, `apps/api`, `packages/`, and `services/`. The repo must be ready for the rest of the build to land into it across multiple disciplines (TypeScript, Python, Rust), multiple deployable artefacts (web app, FastAPI gateway, services), and multiple regions.

This decision is foundation only. It does not commit any infrastructure, CI/CD, database, auth, or product feature.

## Options considered

### Option A: Turborepo with pnpm workspaces (chosen)

- Pros: cleanly handles multiple languages via task orchestration without language opinionation, pnpm content addressed store keeps installs fast and disk lean, large prior art in similar audit grade products.
- Cons: turbo cache discipline must be maintained as the repo grows, Python and Rust still need their own tooling alongside.
- Cost: zero license cost, low onboarding cost for engineers familiar with modern JS tooling.
- Reversibility: hybrid. Swapping monorepo tools later is possible but expensive. The pnpm workspaces choice in particular is sticky.

### Option B: Nx with pnpm workspaces

- Pros: stronger built in support for multi language projects, more sophisticated dependency graph.
- Cons: heavier, more opinionated, larger learning curve for a tiny founding team.
- Cost: zero license cost for community edition, higher cognitive cost.
- Reversibility: hybrid.

### Option C: Polyrepo (one repo per service)

- Pros: each service owns its own CI and release.
- Cons: massive coordination overhead at this stage, breaks cross language refactoring.
- Cost: high, especially for the founding team.
- Reversibility: two way for small fan out, one way for large fan out.

## Decision

Adopt Option A. Turborepo with pnpm workspaces, single Verolas monorepo. Workspace globs follow `apps/*`, `packages/*`, `services/*` per `pnpm-workspace.yaml`.

## Consequences

Positive:

- One clone, one install, one place to search for any code.
- Turborepo can orchestrate cross workspace tasks even when the underlying tool is `cargo`, `uv`, `poetry`, or `pytest`. We model those non Node packages by giving them a thin `package.json` shim that calls into their native tooling.
- The first product workstreams land cleanly into this layout without restructuring.

Negative:

- All engineers must know pnpm and turbo, even those working only in Python or Rust.
- Cache invalidation discipline (correct `outputs` arrays in `turbo.json`) must be maintained as new packages are added.

New work created:

- Lands the GitHub Actions pipelines that drive `turbo run` in CI, with self hosted runners on Hetzner.
- Introduces the FastAPI app under `apps/api`, which will use a `package.json` shim plus `pyproject.toml`.
- Introduces the first Rust crate under `packages/geometry-kernel` once the geometry workstream begins.

## Compliance and audit notes

No direct compliance impact today. The monorepo layout supports audit grade reproducibility (everything from infra to product is in a single commit graph), which contributes to EU AI Act high risk record keeping obligations once the rest of the platform populates it.

## Follow ups

1. Stand up infrastructure baseline on Hetzner.
2. Wire up CI/CD pipelines and pre commit hooks.
3. Add Conventional Commits enforcement (commitlint or equivalent) when CI lands.

## References

- Turborepo docs: https://turbo.build
- pnpm workspaces docs: https://pnpm.io/workspaces
