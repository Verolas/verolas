"""clamd INSTREAM client.

Speaks the ClamAV daemon TCP protocol directly. No external dependency
beyond the stdlib, so the storage library stays light. The daemon address
is supplied by the caller (typically a Kubernetes Service inside the
cluster).

Protocol summary:
    Send: `zINSTREAM\\0`
    Then repeated frames: <4-byte length big-endian><bytes>
    End: `<0 4-byte zero>`
    Receive: `stream: OK\\0` or `stream: <signature> FOUND\\0` or
             `INSTREAM size limit exceeded. ERROR\\0`

We chunk the file into 64 KiB frames, well under clamd's default
StreamMaxLength.
"""

from __future__ import annotations

import socket
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

_CHUNK_SIZE = 64 * 1024
_RESPONSE_BUFFER = 4096


class ScanVerdict(StrEnum):
    """ClamAV scan outcome categories."""

    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Parsed clamd response."""

    verdict: ScanVerdict
    signature: str | None
    raw: str


@dataclass(frozen=True, slots=True)
class ClamdClient:
    """Minimal blocking client.

    Stateless beyond connection. Each `scan_stream` call opens a fresh TCP
    connection because clamd closes the connection after one INSTREAM. For
    async callers, run via `asyncio.to_thread`.
    """

    host: str
    port: int = 3310
    timeout_seconds: float = 30.0

    def scan_stream(self, chunks: Iterable[bytes]) -> ScanResult:
        """Scan an iterable of chunks. Each chunk is sent as one frame."""
        with socket.create_connection((self.host, self.port), timeout=self.timeout_seconds) as sock:
            sock.sendall(b"zINSTREAM\0")
            for chunk in chunks:
                if not chunk:
                    continue
                if len(chunk) > _CHUNK_SIZE:
                    # Rechunk oversized inputs to stay polite with clamd.
                    for offset in range(0, len(chunk), _CHUNK_SIZE):
                        piece = chunk[offset : offset + _CHUNK_SIZE]
                        sock.sendall(len(piece).to_bytes(4, "big") + piece)
                else:
                    sock.sendall(len(chunk).to_bytes(4, "big") + chunk)
            sock.sendall(b"\0\0\0\0")
            raw = sock.recv(_RESPONSE_BUFFER).decode("ascii", errors="replace").rstrip("\0").strip()
        return _parse_response(raw)

    def ping(self) -> bool:
        """Return True if clamd is reachable and responds with PONG."""
        try:
            with socket.create_connection(
                (self.host, self.port), timeout=self.timeout_seconds
            ) as sock:
                sock.sendall(b"zPING\0")
                response = sock.recv(_RESPONSE_BUFFER).decode("ascii", errors="replace")
            return response.startswith("PONG")
        except OSError:
            return False


def _parse_response(raw: str) -> ScanResult:
    if raw.startswith("stream: ") and raw.endswith("OK"):
        return ScanResult(verdict=ScanVerdict.CLEAN, signature=None, raw=raw)
    if "FOUND" in raw:
        # Format: "stream: <signature> FOUND"
        body = raw.removeprefix("stream: ")
        if " FOUND" in body:
            signature = body[: body.rfind(" FOUND")].strip()
            return ScanResult(verdict=ScanVerdict.INFECTED, signature=signature or None, raw=raw)
    return ScanResult(verdict=ScanVerdict.ERROR, signature=None, raw=raw)


__all__ = ["ClamdClient", "ScanResult", "ScanVerdict"]
