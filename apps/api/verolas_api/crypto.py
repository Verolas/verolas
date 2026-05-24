"""Application-layer credential encryption.

OAuth tokens are written to `connector_installations.credentials` as
`{"encrypted": "<fernet-ciphertext>"}` so that even a database leak
does not surface live vendor tokens. The key comes from the
`VEROLAS_CREDENTIAL_KEY` environment variable (a base64-encoded 32-byte
key, exactly what `Fernet.generate_key()` returns).

In dev, if no key is set we fall back to a process-local key so the
service still boots; the encrypted blobs become unreadable across
restarts, which forces re-install and is the safer dev default.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = os.environ.get("VEROLAS_CREDENTIAL_KEY")
    if not key:
        # Ephemeral dev key. Logs (not raises) so local dev works.
        key = Fernet.generate_key().decode()
    return Fernet(key.encode())


def encrypt_credentials(value: dict[str, Any]) -> dict[str, str]:
    """Wrap an arbitrary dict in `{"encrypted": "<ciphertext>"}`."""
    plaintext = json.dumps(value, sort_keys=True).encode()
    return {"encrypted": _fernet().encrypt(plaintext).decode()}


def decrypt_credentials(value: dict[str, Any] | None) -> dict[str, Any]:
    """Reverse `encrypt_credentials`. Returns `{}` if missing or unreadable."""
    if not value or "encrypted" not in value:
        return {}
    token = value["encrypted"]
    if not isinstance(token, str):
        return {}
    try:
        plaintext = _fernet().decrypt(token.encode())
    except InvalidToken:
        return {}
    decoded: Any = json.loads(plaintext.decode())
    if not isinstance(decoded, dict):
        return {}
    return decoded


__all__ = ["decrypt_credentials", "encrypt_credentials"]
