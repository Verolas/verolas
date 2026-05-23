# Multi stage build for the Verolas FastAPI app.
# Stage 1 installs dependencies into a layered uv managed virtualenv.
# Stage 2 copies the venv plus app source into a slim runtime image.
# The verolas-auth source path dependency requires copying that directory too.

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_PREFERENCE=only-system

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/* \
  && curl -LsSf https://astral.sh/uv/install.sh | sh \
  && mv /root/.local/bin/uv /usr/local/bin/uv \
  && mv /root/.local/bin/uvx /usr/local/bin/uvx

WORKDIR /workspace

COPY services/auth/pyproject.toml services/auth/uv.lock services/auth/README.md services/auth/
COPY services/auth/verolas_auth services/auth/verolas_auth
COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/README.md apps/api/
COPY apps/api/verolas_api apps/api/verolas_api

WORKDIR /workspace/apps/api
RUN uv sync --frozen --no-dev --no-install-project
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/workspace/apps/api/.venv/bin:$PATH"

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates tini \
  && rm -rf /var/lib/apt/lists/* \
  && groupadd --gid 1001 verolas \
  && useradd --uid 1001 --gid 1001 --home /home/verolas --create-home --shell /bin/bash verolas

WORKDIR /workspace/apps/api

COPY --from=builder --chown=verolas:verolas /workspace /workspace

USER verolas

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "verolas_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips=*"]
