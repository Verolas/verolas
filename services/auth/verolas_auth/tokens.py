"""OIDC token verification against the Keycloak issuer.

Every API request carries a bearer token signed by Keycloak. The API verifies
the signature against the realm's JWKS, checks the issuer, audience, and
expiry, then extracts the claims we care about: subject (Keycloak user id),
selected organization, and the roles the user has in that org.

The JWKS is cached for ten minutes by default. The verifier never trusts
unverified claims: the JWKS lookup, signature verification, and exp check
all happen before any claim is read.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any
from uuid import UUID

import httpx
import jwt
from pydantic import BaseModel, Field

from verolas_auth.roles import Role


class TokenVerifierSettings(BaseModel):
    """Configuration loaded from environment by the calling service."""

    issuer: str = Field(description="OIDC issuer URL, e.g. https://auth.verolas.com/realms/verolas")
    audience: str = Field(description="Expected `aud` claim, e.g. verolas-api")
    jwks_cache_ttl_seconds: int = Field(default=600, ge=60)
    http_timeout_seconds: float = Field(default=5.0, ge=0.5)

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer.rstrip('/')}/protocol/openid-connect/certs"


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """The subset of token claims Verolas cares about."""

    keycloak_subject: str
    email: str
    org_id: UUID | None
    roles: tuple[Role, ...]
    issued_at: int
    expires_at: int


@dataclass
class _JwksCache:
    """In memory JWKS cache keyed by kid."""

    keys: dict[str, Any] = field(default_factory=dict)
    fetched_at: float = 0.0
    lock: Lock = field(default_factory=Lock)


class TokenVerifier:
    """Verifies OIDC access tokens and returns parsed claims."""

    def __init__(
        self,
        settings: TokenVerifierSettings,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._http = http_client or httpx.Client(timeout=settings.http_timeout_seconds)
        self._cache = _JwksCache()

    def verify(self, token: str) -> TokenClaims:
        """Verify a bearer token; raise jwt.InvalidTokenError on failure."""
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not isinstance(kid, str):
            raise jwt.InvalidTokenError("Token header is missing the kid field.")

        signing_key = self._signing_key_for(kid)
        decoded: dict[str, Any] = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256", "ES256"],
            audience=self._settings.audience,
            issuer=self._settings.issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
        return self._claims_from_decoded(decoded)

    def _signing_key_for(self, kid: str) -> Any:
        with self._cache.lock:
            age = time.monotonic() - self._cache.fetched_at
            if kid not in self._cache.keys or age > self._settings.jwks_cache_ttl_seconds:
                self._refresh_jwks_locked()
            try:
                return self._cache.keys[kid]
            except KeyError:
                raise jwt.InvalidTokenError(
                    f"Token signed with unknown key id {kid}; JWKS does not advertise it."
                ) from None

    def _refresh_jwks_locked(self) -> None:
        response = self._http.get(self._settings.jwks_url)
        response.raise_for_status()
        payload = response.json()
        keys: dict[str, Any] = {}
        for key in payload.get("keys", []):
            kid = key.get("kid")
            if not isinstance(kid, str):
                continue
            if key.get("use") not in (None, "sig"):
                continue
            try:
                keys[kid] = jwt.PyJWK(key).key
            except jwt.PyJWKError:
                continue
        self._cache.keys = keys
        self._cache.fetched_at = time.monotonic()

    @staticmethod
    def _claims_from_decoded(decoded: dict[str, Any]) -> TokenClaims:
        raw_roles = decoded.get("verolas_roles", [])
        if not isinstance(raw_roles, list):
            raw_roles = []
        parsed_roles: list[Role] = []
        for r in raw_roles:
            if isinstance(r, str):
                try:
                    parsed_roles.append(Role(r))
                except ValueError:
                    continue

        org_id_raw = decoded.get("verolas_org_id")
        org_id: UUID | None = None
        if isinstance(org_id_raw, str):
            try:
                org_id = UUID(org_id_raw)
            except ValueError:
                org_id = None

        return TokenClaims(
            keycloak_subject=str(decoded["sub"]),
            email=str(decoded.get("email", "")),
            org_id=org_id,
            roles=tuple(parsed_roles),
            issued_at=int(decoded["iat"]),
            expires_at=int(decoded["exp"]),
        )
