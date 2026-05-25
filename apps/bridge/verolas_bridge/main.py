"""Entry point. Reads settings, opens an http client, runs forever."""

from __future__ import annotations

import asyncio
import logging
import sys

import structlog

from verolas_bridge.client import BridgeClient
from verolas_bridge.runner import run_forever
from verolas_bridge.settings import BridgeSettings
from verolas_bridge.tools import bootstrap_tools


def _configure_logging(level: str, json: bool) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    structlog.configure(processors=processors, cache_logger_on_first_use=True)


async def _amain() -> None:
    settings = BridgeSettings()  # type: ignore[call-arg]
    _configure_logging(settings.log_level, settings.log_json)
    bootstrap_tools()
    log = structlog.get_logger("verolas_bridge")
    log.info(
        "bridge_starting",
        api_base_url=settings.api_base_url,
        poll_interval_seconds=settings.poll_interval_seconds,
        hostname=settings.hostname,
    )
    client = BridgeClient(api_base_url=settings.api_base_url, token=settings.token)
    try:
        await run_forever(client, settings.poll_interval_seconds)
    finally:
        await client.aclose()


def main() -> None:
    """Module entry point used by `python -m verolas_bridge.main`."""
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
