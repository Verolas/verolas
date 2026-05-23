"""clamd response parser tests.

We do not stand up a real clamd. The parser is the testable surface; the
socket plumbing in `scan_stream` is exercised in integration tests against
a real ClamAV pod once the cluster has one running.
"""

from __future__ import annotations

from verolas_storage.clamd import ScanVerdict
from verolas_storage.clamd import _parse_response as parse_response


def test_clean_response() -> None:
    result = parse_response("stream: OK")
    assert result.verdict is ScanVerdict.CLEAN
    assert result.signature is None


def test_infected_response_extracts_signature() -> None:
    result = parse_response("stream: Eicar-Test-Signature FOUND")
    assert result.verdict is ScanVerdict.INFECTED
    assert result.signature == "Eicar-Test-Signature"


def test_error_response_falls_through() -> None:
    result = parse_response("INSTREAM size limit exceeded. ERROR")
    assert result.verdict is ScanVerdict.ERROR
