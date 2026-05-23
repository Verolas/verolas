"""Smoke tests for the migrations package."""

from __future__ import annotations

import importlib


def test_package_imports() -> None:
    """The db_migrations package imports cleanly."""
    module = importlib.import_module("db_migrations")
    assert module.__version__ == "0.0.0"


def test_alembic_config_exists() -> None:
    """alembic.ini is present at the project root."""
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1]
    assert (project_root / "alembic.ini").is_file()
    assert (project_root / "alembic" / "env.py").is_file()
    assert (project_root / "alembic" / "versions").is_dir()
