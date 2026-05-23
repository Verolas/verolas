# @verolas/web

Verolas web app. Next.js 15 App Router, React 19, TypeScript strict, Tailwind 4, shadcn primitives, IBM Plex fonts, axe powered WCAG 2.2 AA baseline.

## Local development

```bash
cd apps/web
pnpm install
pnpm dev
```

Visit http://localhost:3000 for the app and http://localhost:6006 for Storybook (`pnpm storybook`).

## Scripts

| Command | Purpose |
| --- | --- |
| `pnpm dev` | Next dev server on port 3000 with hot reload |
| `pnpm build` | Production build with React server components compiled |
| `pnpm start` | Run the production build |
| `pnpm lint` | ESLint with the Next config plus `jsx-a11y` rules |
| `pnpm typecheck` | `tsc --noEmit` with strict and exactOptionalPropertyTypes |
| `pnpm test:e2e` | Playwright suite including axe accessibility checks against every rendered page |
| `pnpm storybook` | Storybook dev server with the a11y addon |
| `pnpm storybook:build` | Static Storybook for deploy to a docs surface |

## Accessibility

The Playwright suite runs `@axe-core/playwright` on every public page with the WCAG 2.2 AA ruleset. Any violation fails the build. Storybook also includes the `@storybook/addon-a11y` panel for per component review during component authoring.

## Brand and tokens

Design tokens live in `src/app/globals.css` under the Tailwind 4 `@theme` block. IBM Plex Sans for body and Plex Mono for code, both loaded via `next/font/google` with `display: swap`. The primary brand colour is the Verolas mid blue (`--color-verolas-mid`); deep and soft variants live alongside.

## Structure

```
src/
  app/
    layout.tsx                 root layout with fonts and metadata
    page.tsx                   redirects to /login
    globals.css                Tailwind 4 import plus @theme tokens
    (auth)/
      login/page.tsx           sign in screen
    (app)/
      layout.tsx               authenticated chrome
      dashboard/page.tsx       at a glance for the active org
      projects/page.tsx        project list
  components/
    ui/                        shadcn primitives (button, card, input, label)
    header.tsx                 app header
    sidebar.tsx                app nav
  lib/
    utils.ts                   cn() class merger
  stories/                     Storybook stories per component
```

## Auth

The first real OIDC PKCE wire up against Keycloak lands in a follow up workstream. Today the login screen is a static skeleton; clicking continue does not yet redirect.

## Dockerfile

Multi stage standalone Next build, runtime on `gcr.io/distroless/nodejs22-debian12` non root. The image workflow at `.github/workflows/image.yml` builds it and signs with Cosign.
