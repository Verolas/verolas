# Verolas

The vertical agentic AI platform for civil engineering. Verolas turns codified design rules (Eurocodes, DIN, ASCE, ACI, AISC) and a firm's own engineering memory into a production grade workflow surface, supervised by a licensed engineer who keeps authorship and liability.

Status: foundation setup. The repo is freshly initialized. Real product code lands as each workstream comes online.

## Mission

Make every structural calculation, geotechnical analysis, hydraulic design, infrastructure permit, and engineering deliverable in the modern built environment produced, reviewed, or validated by a Verolas agent under the supervision of a licensed engineer.

Liability stays human. Productivity becomes superhuman.

## Architecture at a glance

Five layers, split universal versus regional:

1. AI infrastructure (LLM gateway, embeddings, vector store, agent framework)
2. Engineering primitives (geometry, materials, FEA, code semantics)
3. Design code modules (EN 1992, EN 1993, EN 1997, ASCE 7, ACI 318, others)
4. Deliverables and workflows (Statik, Bewehrungsplan, Baugrundgutachten, permit packs)
5. Language and UX (Assistant, Vault, Research, Workflows, Connect)

Six products: Structural, Geotech, Water, Transport, Review, Practice.
Five surfaces: Assistant, Vault, Research, Workflows, Connect.

Region first rollout. The first wave targets DACH (Germany, Austria, Switzerland).

## Repository layout

This is a Turborepo monorepo using pnpm workspaces.

```
apps/
  web/        Next.js 15 web app
  api/        FastAPI gateway
packages/
  config/     Shared TS, lint, format, Tailwind config
  ui/         Shared design system primitives consumed by apps/web
services/     Independently deployed runtime services
docs/
  decisions/  Architecture Decision Records (ADRs)
```

The directories ship as placeholders today and fill in as their workstreams come online.

## Tech stack baseline

- Frontend: Next.js 15, React 19, TypeScript strict, Tailwind 4, shadcn primitives
- Backend: Python 3.12 with FastAPI plus Rust hot paths
- Data: PostgreSQL 17, Qdrant, Redis, S3 compatible object storage
- AI: multi provider LLM gateway, Anthropic Claude primary, EU sovereign fallbacks
- Orchestration: Kubernetes, Temporal, Argo CD
- Hosting: Hetzner EU sovereign primary, Cloudflare edge

## Local development

Prerequisites:

- Node.js 22 or newer (`.nvmrc` pins to 22)
- pnpm 10 or newer
- Python 3.12 or newer (for `apps/api`)
- Rust toolchain (for performance crates)

Install and verify:

```bash
pnpm install
pnpm typecheck
pnpm lint
pnpm test
```

The placeholders only echo today, so commands complete quickly. Real builds light up as each workstream comes online.

## Contributing

See `CONTRIBUTING.md` for the founding team workflow, branch model, PR review policy, and coding conventions. New architectural decisions are captured as ADRs in `docs/decisions/`.

## License

Proprietary. All rights reserved. See `LICENSE`.

## Contact

Founding team only at this stage. For partnership and pilot inquiries: hello@verolas.com.
