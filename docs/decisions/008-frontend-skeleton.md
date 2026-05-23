# ADR 008: Frontend skeleton, Next.js 15, Tailwind 4, shadcn primitives, axe accessibility baseline

- Status: accepted
- Date: 2026-05-23
- Deciders: Shramish Kafle (founder, CEO)
- Consulted: ADR 001, ADR 003, ADR 005, ADR 006
- Informed: founding team

## Context

Verolas is an engineer facing product. The web surface is where users review deliverables, sign off as engineer of record, and drive workflows. Get the skeleton right once: framework, styling system, primitives, fonts, accessibility, build pipeline. Every feature page that lands afterward inherits the same posture without rediscovering it.

## Options considered

### Framework: Next.js 15 App Router (chosen)

- Pros: the bible mandates it. React 19 first class support, server components by default, the App Router gives us nested layouts and per route loading and error UI for free. The standalone build output ships exactly the code the runtime needs.
- Cons: server component patterns are still in motion across the ecosystem, the third party UI libraries we add later need to support React 19.

### Styling: Tailwind 4 with CSS first config (chosen)

- Pros: also mandated by the bible. The v4 CSS-first config via `@theme` is faster to author, no tailwind.config.js to maintain, and design tokens live in `globals.css` next to the components they style. Tree shaking is excellent.
- Cons: v4 is recent; tooling that lags (Storybook addons, linters) needs explicit version selection.

### Primitives: shadcn style components copied into the codebase (chosen)

- Pros: we own the source of every primitive. No version pin to a third party design system that drifts under us. Radix UI underneath gives the right ARIA semantics by default.
- Cons: we maintain the components ourselves. Mitigation: the surface stays small until product features warrant more.

### Fonts: IBM Plex Sans plus IBM Plex Mono via next/font (chosen)

- Pros: open source, broad language coverage including German diacritics, distinct engineering feel that matches the bible's brand direction. `next/font/google` self hosts the font files so we serve them on our own domain, satisfying the EU sovereign posture without a third party CDN hop.
- Cons: an additional roughly 200 KB transferred on first paint. Acceptable.

### Accessibility: axe powered Playwright suite plus jsx-a11y ESLint plus Storybook a11y addon (chosen)

- Pros: three independent gates. The eslint plugin catches static issues at edit time. The Storybook addon catches issues during component authoring. The Playwright suite enforces WCAG 2.2 AA on every rendered page; any violation fails CI.
- Cons: axe finds about 30 percent of real WCAG failures. Manual audits are still needed. Acceptable as a baseline.

### Build pipeline: existing image workflow, Dockerfile uses Next standalone on distroless (chosen)

- Pros: image workflow already discovers Dockerfiles in `apps/*`. The standalone output keeps the runtime image small. Distroless Node 22 nonroot is the conservative pick for the runtime.
- Cons: standalone output assumes node_modules layout that matches the build; the Dockerfile copies the static assets explicitly to handle this.

## Decision

| Bible bullet | Implementation |
| --- | --- |
| Next.js 15 App Router scaffolding | `apps/web/src/app/` with grouped routes for `(auth)` and `(app)` |
| Tailwind 4 + design tokens (Part 10 colors, IBM Plex fonts) | `src/app/globals.css` with `@theme` block, fonts loaded via `next/font` |
| shadcn/ui base components | `src/components/ui/` Button, Card, Input, Label with cva and Radix Slot |
| Storybook for component library | `.storybook/` config plus stories for Button and Card. `@storybook/addon-a11y` enabled. |
| First skeleton pages: login, dashboard, project list | `(auth)/login/page.tsx`, `(app)/dashboard/page.tsx`, `(app)/projects/page.tsx` |
| Accessibility baseline (WCAG 2.2 AA) wired into CI | `@axe-core/playwright` checks on every page in `tests/e2e/smoke.spec.ts`. `eslint-plugin-jsx-a11y` enforced via `pnpm lint`. |

Build artefacts:

- Multi stage Dockerfile producing a distroless Node 22 nonroot image
- Kubernetes Deployment with non root, read only fs, all caps dropped, seccomp `RuntimeDefault`
- Traefik IngressRoute at `app.dev.verolas.com` with a Middleware that sets security headers including CSP

## Consequences

Positive:

- Every page renders WCAG 2.2 AA clean today. New pages inherit the lint, the Storybook gate, and the Playwright gate without per page work.
- shadcn style components live in our repo, so we own the design system. No upstream churn to chase.
- The build container is small, distroless, non root from day one. The deploy posture matches the api pod.

Negative:

- React 19 and Tailwind 4 are recent enough that some libraries we may want later have not caught up. We pick libraries that already support both.
- The login page is static; the OIDC PKCE redirect to Keycloak lands in a follow up alongside the verolas-auth integration on the client.

New work created:

- Wire OIDC PKCE on the login page. Use the `verolas-web` Keycloak client from ADR 005.
- Replace the dashboard and projects placeholder data with real API calls once the database wiring on apps/api lands.
- Add the trust ladder component (per the bible, Part 3.2) when the workflow surface lands.
- Add a German locale via `next-intl`; the architecture in ADR 001 expects DACH primary.

## Compliance and audit notes

- WCAG 2.2 AA is the EN 301 549 baseline for the European Accessibility Act. Enforced in CI from day one, before any customer can hit the surface.
- `robots: noindex, nofollow` in metadata prevents the dev and staging deployments from leaking into search engines.
- CSP at the ingress middleware caps third party content sources. Future external integrations require explicit CSP additions in this file.

## Follow ups

1. Wire OIDC PKCE against the `verolas-web` realm client.
2. Add `next-intl` and German locale; the bible mandates bilingual UI for DACH.
3. Add the trust ladder component plus the first deliverable detail page.
4. Tighten CSP from `unsafe-inline` to nonce based once production logging surfaces an injection attempt or the React SSR pipeline stabilises.
5. Add visual regression checks via Chromatic, hooked into the existing Storybook build.

## References

- Next.js 15: https://nextjs.org
- Tailwind CSS 4: https://tailwindcss.com
- shadcn/ui: https://ui.shadcn.com
- IBM Plex: https://www.ibm.com/plex
- WCAG 2.2: https://www.w3.org/TR/WCAG22/
- axe-core: https://github.com/dequelabs/axe-core
- EN 301 549 (European Accessibility Act): https://en.wikipedia.org/wiki/EN_301_549
- Related: [[ADR 001]], [[ADR 003]], [[ADR 005]], [[ADR 006]]
