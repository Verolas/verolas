"""Tests for the OIDC token verifier.

We do not call a live Keycloak. Instead we mint our own RSA key pair, sign a
token with it, stub the JWKS HTTP response to expose the public key under a
known kid, and verify the token through the public API of TokenVerifier.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from verolas_auth.roles import Role
from verolas_auth.tokens import TokenVerifier, TokenVerifierSettings


@pytest.fixture
def issuer() -> str:
    return "https://auth.test.local/realms/verolas"


@pytest.fixture
def audience() -> str:
    return "verolas-api"


@pytest.fixture
def rsa_keypair() -> tuple[rsa.RSAPrivateKey, dict[str, Any]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    import base64

    def b64url_uint(value: int) -> str:
        length = max(1, (value.bit_length() + 7) // 8)
        return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode("ascii")

    jwk = {
        "kty": "RSA",
        "kid": "test-key-1",
        "use": "sig",
        "alg": "RS256",
        "n": b64url_uint(public_numbers.n),
        "e": b64url_uint(public_numbers.e),
    }
    return private_key, jwk


def _sign(
    private_key: rsa.RSAPrivateKey,
    *,
    iss: str,
    aud: str,
    sub: str,
    roles: list[str] | None = None,
    org_id: str | None = None,
    email: str = "user@example.com",
) -> str:
    now = int(time.time())
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    payload: dict[str, Any] = {
        "iss": iss,
        "aud": aud,
        "sub": sub,
        "email": email,
        "iat": now,
        "exp": now + 300,
        "verolas_roles": roles or [],
    }
    if org_id is not None:
        payload["verolas_org_id"] = org_id
    return jwt.encode(payload, pem, algorithm="RS256", headers={"kid": "test-key-1"})


def _verifier_with_jwks(issuer: str, audience: str, jwk: dict[str, Any]) -> TokenVerifier:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": [jwk]})

    transport = httpx.MockTransport(handler)
    return TokenVerifier(
        TokenVerifierSettings(issuer=issuer, audience=audience),
        http_client=httpx.Client(transport=transport, timeout=2.0),
    )


def test_verify_returns_claims_for_valid_token(
    issuer: str, audience: str, rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]]
) -> None:
    private_key, jwk = rsa_keypair
    token = _sign(
        private_key,
        iss=issuer,
        aud=audience,
        sub="kc-subject-123",
        roles=["owner", "engineer"],
        org_id="00000000-0000-4000-8000-000000000abc",
        email="founder@verolas.com",
    )
    verifier = _verifier_with_jwks(issuer, audience, jwk)
    claims = verifier.verify(token)
    assert claims.keycloak_subject == "kc-subject-123"
    assert claims.email == "founder@verolas.com"
    assert claims.org_id == UUID("00000000-0000-4000-8000-000000000abc")
    assert Role.OWNER in claims.roles
    assert Role.ENGINEER in claims.roles


def test_verify_rejects_wrong_audience(
    issuer: str, audience: str, rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]]
) -> None:
    private_key, jwk = rsa_keypair
    token = _sign(private_key, iss=issuer, aud="other-audience", sub="sub")
    verifier = _verifier_with_jwks(issuer, audience, jwk)
    with pytest.raises(jwt.InvalidAudienceError):
        verifier.verify(token)


def test_verify_rejects_wrong_issuer(
    issuer: str, audience: str, rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]]
) -> None:
    private_key, jwk = rsa_keypair
    token = _sign(private_key, iss="https://evil.example", aud=audience, sub="sub")
    verifier = _verifier_with_jwks(issuer, audience, jwk)
    with pytest.raises(jwt.InvalidIssuerError):
        verifier.verify(token)


def test_verify_rejects_unknown_kid(
    issuer: str, audience: str, rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]]
) -> None:
    private_key, jwk = rsa_keypair
    different_kid = dict(jwk)
    different_kid["kid"] = "some-other-kid"
    token = _sign(private_key, iss=issuer, aud=audience, sub="sub")
    verifier = _verifier_with_jwks(issuer, audience, different_kid)
    with pytest.raises(jwt.InvalidTokenError):
        verifier.verify(token)


def test_verify_drops_invalid_role_strings(
    issuer: str, audience: str, rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]]
) -> None:
    private_key, jwk = rsa_keypair
    token = _sign(
        private_key,
        iss=issuer,
        aud=audience,
        sub="sub",
        roles=["owner", "not-a-real-role", "viewer"],
    )
    verifier = _verifier_with_jwks(issuer, audience, jwk)
    claims = verifier.verify(token)
    assert claims.roles == (Role.OWNER, Role.VIEWER)
