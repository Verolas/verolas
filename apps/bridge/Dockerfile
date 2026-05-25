# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS build
WORKDIR /workspace/apps/bridge

RUN pip install --no-cache-dir uv==0.5.0

COPY apps/bridge/pyproject.toml .
COPY apps/bridge/verolas_bridge ./verolas_bridge
RUN uv sync --frozen --no-dev || uv sync --no-dev

FROM python:3.12-slim AS runtime
WORKDIR /workspace/apps/bridge

# Run as non-root.
RUN groupadd --system --gid 1000 verolas && \
    useradd --system --uid 1000 --gid verolas --create-home verolas

COPY --from=build --chown=verolas:verolas /workspace/apps/bridge /workspace/apps/bridge

USER verolas
ENV PYTHONUNBUFFERED=1
CMD ["/workspace/apps/bridge/.venv/bin/python", "-m", "verolas_bridge.main"]
