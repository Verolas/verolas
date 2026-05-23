# Multi stage build for the Verolas web app.
# Stage 1 builds the Next.js standalone output.
# Stage 2 packages it onto a distroless Node 22 runtime, non root.

FROM node:22-bookworm-slim AS builder

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH

RUN corepack enable && corepack prepare pnpm@10.27.0 --activate

WORKDIR /workspace

# Copy workspace metadata so pnpm sees the monorepo shape, then the web app
# itself. Other workspaces are intentionally omitted; the web app does not
# depend on them today.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/

RUN pnpm install --frozen-lockfile --filter @verolas/web...

COPY apps/web apps/web

WORKDIR /workspace/apps/web

RUN pnpm build

FROM gcr.io/distroless/nodejs22-debian12:nonroot AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

WORKDIR /app

COPY --from=builder --chown=nonroot:nonroot /workspace/apps/web/.next/standalone /app
COPY --from=builder --chown=nonroot:nonroot /workspace/apps/web/.next/static /app/apps/web/.next/static
COPY --from=builder --chown=nonroot:nonroot /workspace/apps/web/public /app/apps/web/public

EXPOSE 3000

CMD ["apps/web/server.js"]
