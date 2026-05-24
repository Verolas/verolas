"""Unit tests for the credential encryption helper + OAuth config catalog."""

from __future__ import annotations

import os

from verolas_api.connector_oauth import OAUTH_CONFIGS, oauth_config
from verolas_api.crypto import decrypt_credentials, encrypt_credentials


def test_oauth_catalog_covers_known_tier_a_classes() -> None:
    # Spot-check a handful of the catalog entries are wired.
    for class_id in (
        "ms-sharepoint",
        "google-drive",
        "slack",
        "procore",
        "docusign",
        "autodesk-aps",
    ):
        cfg = oauth_config(class_id)
        assert cfg is not None, f"Tier A connector {class_id} has no OAuth config"
        assert cfg.authorize_url.startswith("https://")
        assert cfg.token_url.startswith("https://")
        assert cfg.client_id_env
        assert cfg.client_secret_env


def test_oauth_catalog_has_no_duplicates() -> None:
    ids = list(OAUTH_CONFIGS.keys())
    assert len(ids) == len(set(ids))


def test_encrypt_and_decrypt_roundtrip() -> None:
    plain = {"access_token": "abc", "refresh_token": "xyz", "expires_in": 3600}
    enc = encrypt_credentials(plain)
    assert "encrypted" in enc
    assert enc["encrypted"] != plain["access_token"]
    out = decrypt_credentials(enc)
    assert out == plain


def test_decrypt_empty_returns_empty() -> None:
    assert decrypt_credentials(None) == {}
    assert decrypt_credentials({}) == {}
    assert decrypt_credentials({"encrypted": ""}) == {}


def test_decrypt_garbled_returns_empty() -> None:
    assert decrypt_credentials({"encrypted": "not-a-real-fernet-token"}) == {}


def test_crypto_uses_env_key_if_provided(monkeypatch) -> None:
    from cryptography.fernet import Fernet

    monkeypatch.setenv("VEROLAS_CREDENTIAL_KEY", Fernet.generate_key().decode())
    # Reset the lru_cache to pick up the env var.
    from verolas_api import crypto

    crypto._fernet.cache_clear()
    enc = encrypt_credentials({"hello": "world"})
    assert decrypt_credentials(enc) == {"hello": "world"}
    # And clear again so the rest of the suite picks up its own key.
    crypto._fernet.cache_clear()
    if "VEROLAS_CREDENTIAL_KEY" in os.environ:
        del os.environ["VEROLAS_CREDENTIAL_KEY"]
