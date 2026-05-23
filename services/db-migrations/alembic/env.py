"""Alembic environment for Verolas.

Reads the connection string from VEROLAS_DATABASE_URL at runtime so the same
migrations apply against dev, staging, and prod from a single source. SQLAlchemy
metadata is empty for now; once application models exist, point target_metadata
at the imported `Base.metadata` to get autogenerate support.
"""

from __future__ import annotations

import logging
import os
from logging.config import fileConfig
from typing import TYPE_CHECKING

from sqlalchemy import engine_from_config, pool

from alembic import context

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

logger = logging.getLogger("alembic.env")

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.environ.get("VEROLAS_DATABASE_URL")
if database_url is None:
    raise RuntimeError(
        "VEROLAS_DATABASE_URL is not set. Export it before running alembic, "
        "for example: postgresql+psycopg://user:pass@host:5432/verolas"
    )
config.set_main_option("sqlalchemy.url", database_url)

# When application models exist, replace None with the Base.metadata import:
#   from verolas_api.models import Base
#   target_metadata = Base.metadata
target_metadata = None


def run_migrations_offline() -> None:
    """Render migrations to SQL without connecting to the database."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Apply migrations against an open database connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations by connecting to the database directly."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
