# Verolas Coding Conventions

This document covers the rules every contributor follows across TypeScript, Python, and Rust. Lint rules and pre commit hooks will enforce most of it once CI is wired up. Until then, follow it by habit and call it out in review.

## Universal rules

1. **No prose dashes.** Do not use em dashes, en dashes, or double hyphens anywhere, including code comments, commit messages, identifiers, log strings, UI strings, and docs. Use a comma, period, colon, parentheses, or restructure the sentence.
2. **Cite engineering claims.** Any function or prompt that produces or relies on an engineering value must carry a docstring citation to the clause, section, table, or formula it implements (for example, "per EN 1992-1-1 §6.4.3" or "ASCE 7-22 Table 12.2-1").
3. **Comment the why, never the what.** If a well named identifier already describes what the code does, do not restate it in a comment. Reserve comments for non obvious constraints, invariants, regulatory rules, or workarounds.
4. **No dead code.** Delete unused exports, types, vars, and imports. Do not leave commented out blocks.
5. **No silent fallbacks.** If a tool, model, or service is unavailable, log a structured error and either retry with backoff or fail loudly. Never substitute a default that could change the engineering meaning of an output.
6. **Deterministic outputs.** Engineering calculations must be reproducible. Seed randomness, pin model versions, capture inputs and intermediate state for audit replay.

## TypeScript

- Strict mode on. `tsconfig.base.json` is the single source of truth for compiler options. Workspace tsconfigs extend it.
- No `any`, no `as unknown as`, no `@ts-ignore` without a one line comment explaining why.
- Prefer types over interfaces, except when extending external library interfaces.
- Imports use absolute paths via TS path aliases inside a workspace, relative paths only for sibling files in the same module.
- Named exports only. No default exports outside Next.js page or route conventions.
- Components are typed function components, never class components.
- Errors are typed. Throw `Error` subclasses, never strings or plain objects.
- React: server components by default, client components only when they need interactivity, browser APIs, or React state.
- Forms use React Hook Form plus Zod. Validation rules live in shared Zod schemas.
- Date and number formatting respects locale. German uses `1.234,56` and `DD.MM.YYYY`.

## Python

- Python 3.12 or newer.
- Type hints required on every public function, every method, every class attribute. Use `from __future__ import annotations` where it helps.
- Lint and format with Ruff. Type check with mypy in strict mode.
- Pydantic v2 models for all API request and response shapes, all agent tool schemas, and all configuration.
- FastAPI route handlers stay thin. Business logic lives in service modules. Engineering logic lives in domain packages.
- Use `uv` or `poetry` for dependency management (decision to be locked in by an ADR before the backend workstream begins).
- No bare `except`. Catch specific exception types.
- Logging via `structlog`, never `print`.
- Float comparisons use explicit tolerance. Never `==` on floats in engineering code.

## Rust

- Stable toolchain, current MSRV pinned per crate in `Cargo.toml`.
- `#![deny(unsafe_op_in_unsafe_fn)]`, `#![warn(missing_docs)]` on every crate.
- Errors via `thiserror` or `anyhow` consistently within a crate, never both.
- Public APIs return `Result`, not panic. Panics are bugs.
- All public functions documented with `///` doc comments plus an `# Examples` section that compiles.
- `cargo clippy` runs against all targets and all features in CI once it is wired up, with warnings treated as errors.

## Naming

- Files and directories use kebab case for TS workspaces (`agent-runner.ts`), snake case for Python (`agent_runner.py`), snake case for Rust (`agent_runner.rs`).
- Types in TS and structs in Rust use PascalCase, functions and variables use camelCase in TS, snake_case in Python and Rust.
- Acronyms in identifiers follow the host language convention (TS: `apiClient`, Python: `api_client`).
- Booleans read like predicates: `isReady`, `hasCitation`, `is_loaded`.

## Engineering domain naming

When an identifier maps to a code clause or a regional standard, encode it explicitly:

- TS: `calcShearCapacityEC2_6_2_2` is acceptable for code clause references. Prefer a function named for the engineering concept with the clause cited in a docstring.
- Python: same, snake case.
- Avoid baking the regional code into a function name when the function is universal. Place region specific logic behind a code module boundary.

## Folder structure inside a workspace

```
src/
  index.ts                     barrel for public exports only
  <feature>/
    <feature>.ts               implementation
    <feature>.test.ts          colocated tests
    types.ts                   types specific to this feature
    schemas.ts                 zod schemas
    README.md                  optional, for non obvious modules
```

Python and Rust mirror this pattern using their native conventions.

## Tests

- Tests live next to the code they test.
- Engineering calculations must have a canonical worked example test fed by Schneider Bautabellen, Wendehorst, ACI 318 design aids, or equivalent.
- No test depends on network access in unit mode. Integration tests are clearly tagged and run on real services in CI once it is wired up.

## Pre commit hooks (added when CI is wired up)

Targeted minimum:

- gitleaks for secret scanning
- Prettier for TS, JS, JSON, YAML, Markdown
- Ruff for Python format and lint
- rustfmt for Rust
- A script that fails on em dashes, en dashes, or double hyphens anywhere in staged files

## When in doubt

Match the style of the surrounding code. If the surrounding code disagrees with this document, open a PR or an ADR.
