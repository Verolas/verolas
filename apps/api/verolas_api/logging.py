"""Structured logging setup.

We use structlog with two renderer paths: pretty console for local dev and
JSON for everything else. Standard library logging is bridged so libraries
that use `logging.getLogger` flow through the same pipeline.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str, json_output: bool) -> None:
    """Configure structlog and the stdlib logging bridge.

    Idempotent. Safe to call from the app factory at startup.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        shared_processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Bridge stdlib logging into structlog.
    logging.basicConfig(level=numeric_level, format="%(message)s", stream=sys.stdout)
