"""Time based one time password helpers.

Verolas enforces TOTP MFA on every user from day one. The Keycloak realm
template configures the OTP policy on the IdP side. This module covers the
small set of operations the application itself performs: generating an
enrollment secret, rendering the provisioning URI a user scans into their
authenticator app, and verifying the code the user types in.
"""

from __future__ import annotations

from dataclasses import dataclass

import pyotp


@dataclass(frozen=True, slots=True)
class MfaProvisioning:
    """Everything a user needs to enroll a new authenticator."""

    secret: str
    provisioning_uri: str


def generate_totp_secret(account_name: str, issuer: str = "Verolas") -> MfaProvisioning:
    """Mint a new TOTP secret and produce the provisioning URI for enrollment.

    `account_name` is shown in the user's authenticator app, typically their
    email. `issuer` is the realm or product name.

    The returned secret is plaintext; the caller is responsible for storing
    it encrypted (Postgres column `users.totp_secret_encrypted` is binary, the
    app envelopes it with libsodium or AES GCM keyed from the founder vault
    in Vault).
    """
    secret = pyotp.random_base32(length=32)
    uri = pyotp.totp.TOTP(secret, digits=6, interval=30).provisioning_uri(
        name=account_name,
        issuer_name=issuer,
    )
    return MfaProvisioning(secret=secret, provisioning_uri=uri)


def verify_totp_code(secret: str, code: str, *, valid_window: int = 1) -> bool:
    """Verify a TOTP code against the user's secret.

    `valid_window` is the number of 30 second steps tolerated on either side
    of the current step. Default 1 step covers clock drift up to 30 seconds.

    pyotp's `verify()` is already constant time. We pre filter malformed input
    so a typo in the client returns False without involving the verifier.
    """
    if not code.isdigit() or len(code) != 6:
        return False
    return pyotp.totp.TOTP(secret, digits=6, interval=30).verify(code, valid_window=valid_window)
