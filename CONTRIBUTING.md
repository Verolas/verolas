# Contributing to Verolas

This document is the founding team workflow. It will tighten as the team grows and as CI lights up. If you are reading this and you are not a current Verolas employee, contractor, or authorized collaborator under a signed agreement, you do not have permission to use, copy, or contribute to this code. See `LICENSE`.

## Ground rules

1. **Engineer supervised, never engineer replacing.** Every output that touches a stampable deliverable must be reviewable, citable, traceable, and stampable by a licensed engineer. We never ship a workflow that hides intermediate reasoning or that cannot be audited end to end.
2. **Cite everything.** Every engineering claim, formula, and clause reference must carry a citation to its source (EN, DIN, ASCE, ACI, AISC, internal memo, or labelled assumption). This applies to code, prompts, evals, and docs.
3. **Audit grade by default.** Assume EU AI Act high risk obligations apply until legal counsel confirms otherwise. Log decisions, preserve inputs, version prompts.
4. **No prose dashes.** Do not use em dashes, en dashes, or double hyphens anywhere in the repo, including code comments, commit messages, PR descriptions, UI strings, and docs. Rewrite the sentence instead.
5. **Private docs stay private.** Files listed in `.gitignore` (including the internal product bible and any local tool config) must never be committed. If you find one staged, unstage and discuss.

## Development environment

Requirements:

- Node.js 22 (see `.nvmrc`)
- pnpm 10
- Python 3.12 (for `apps/api`)
- Rust stable (for performance crates)
- Docker (once CI is wired up)

First time setup:

```bash
nvm use
corepack enable
pnpm install
```

Common scripts:

```bash
pnpm dev         # run all dev tasks across workspaces
pnpm build       # build everything turbo knows about
pnpm typecheck   # TypeScript only
pnpm lint        # lint across workspaces
pnpm test        # all tests
```

These mostly echo placeholders today. Real targets light up as each workstream comes online.

## Branch model

- `main` is protected. Always green, always deployable. No direct pushes.
- Feature branches use the form `type/short-slug`, where `type` is one of:
  - `feat/` new capability
  - `fix/` bug fix
  - `chore/` tooling, deps, repo hygiene
  - `refactor/` no behaviour change
  - `docs/` documentation only
  - `test/` test only
  - `infra/` infrastructure, CI, deployment
  - `adr/` architecture decision record
- Branches are short lived. Aim to merge within five working days. If a branch will live longer, rebase it on `main` at least every other day.
- Squash merge into `main`. The squash commit subject becomes the changelog line for the workstream it advances.

## Pull request policy

Every change goes through a PR. No exceptions, including for founders.

PR checklist (enforced by template once CI lands):

- [ ] One reviewer approval, two for changes that touch agents, prompts, evals, code modules, citations, or anything that could change a stampable deliverable.
- [ ] All CI checks green: typecheck, lint, tests, security scans.
- [ ] If the change introduces or modifies an architectural decision, an ADR is added or updated in `docs/decisions/`.
- [ ] If the change touches user facing strings, both German and English locales are updated.
- [ ] If the change touches an engineering calculation or a prompt that produces one, the eval suite for that workflow ran green.
- [ ] No private docs staged (run `git status` and confirm no internal-only file is listed).
- [ ] PR description explains the why, links the related issue, and includes a screenshot or sample output for any user facing or output facing change.

Reviewers must read the diff, not just the description. For prompt or agent changes, reviewers must inspect the eval delta.

## Commit conventions

Use Conventional Commits style for the squash commit subject:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Type matches the branch type (`feat`, `fix`, `chore`, `refactor`, `docs`, `test`, `infra`, `adr`). Scope is the workspace or area (`web`, `api`, `ui`, `config`, `geometry`, `ec2`, ...).

Rules:

- Subject line under 72 characters, imperative mood, no trailing period.
- No em dashes, en dashes, or double hyphens anywhere in the message.
- Reference the related issue in the body when applicable (for example, "Closes #42").
- Do not add Claude Code, Anthropic, or any AI tool as a co author. Commit messages must show no AI authorship.

## Coding conventions

See `docs/coding-conventions.md` for the full TS, Python, and Rust style rules, naming, and structure.

## Architecture Decision Records

Significant decisions are captured as ADRs.

- Template: `docs/decisions/000-template.md`
- New ADRs are numbered sequentially (`001-...`, `002-...`).
- Status moves through `proposed`, `accepted`, `superseded`, or `deprecated`.
- An ADR is required for any change that locks in a long lived choice (database engine, framework, vendor, sovereignty boundary, agent topology, eval methodology).

## Security and secrets

- Never commit secrets, keys, tokens, customer data, or `.env` files.
- Use environment variables locally. Production secrets land in HashiCorp Vault once the secrets workstream comes online.
- Report a suspected secret leak immediately to the founder team and rotate the credential.

## Branch protection (configured on GitHub, tracked here)

The following rules must be set on `main` once the org plan supports it:

- Require pull request reviews before merging, minimum one approval, two for agent and code module paths.
- Require status checks to pass before merging.
- Require branches to be up to date before merging.
- Require signed commits.
- Restrict who can push to matching branches: nobody, including admins.
- Do not allow force pushes.
- Do not allow deletions.

These rules are tracked here so the configuration can be reproduced after any GitHub UI reset.

## Questions

Open a thread in `#eng` on Slack or message the founder directly.
