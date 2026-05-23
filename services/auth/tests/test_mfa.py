"""Tests for the TOTP MFA helpers."""

from __future__ import annotations

from urllib.parse import unquote

import pyotp

from verolas_auth.mfa import generate_totp_secret, verify_totp_code


def test_generate_totp_secret_returns_uri_and_secret() -> None:
    p = generate_totp_secret("user@example.com", issuer="Verolas")
    assert len(p.secret) >= 16

    uri = unquote(p.provisioning_uri)
    assert uri.startswith("otpauth://totp/")
    assert "issuer=Verolas" in uri
    assert "user@example.com" in uri


def test_verify_totp_code_accepts_current_code() -> None:
    p = generate_totp_secret("user@example.com")
    current = pyotp.totp.TOTP(p.secret, digits=6, interval=30).now()
    assert verify_totp_code(p.secret, current)


def test_verify_totp_code_rejects_malformed_input() -> None:
    p = generate_totp_secret("user@example.com")
    assert not verify_totp_code(p.secret, "abcdef")
    assert not verify_totp_code(p.secret, "12345")
    assert not verify_totp_code(p.secret, "1234567")


def test_verify_totp_code_rejects_wrong_code() -> None:
    p = generate_totp_secret("user@example.com")
    assert not verify_totp_code(p.secret, "000000")
