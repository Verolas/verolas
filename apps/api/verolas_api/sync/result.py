"""Shared shapes for sync engine results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SyncResult:
    """What a single sync run accomplished."""

    files_added: int = 0
    files_updated: int = 0
    files_removed: int = 0
    bytes_pulled: int = 0
    next_cursor: str | None = None
    notes: list[str] = field(default_factory=list)


__all__ = ["SyncResult"]
