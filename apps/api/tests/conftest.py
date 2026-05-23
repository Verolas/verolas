"""Pytest fixtures for the API tests.

We mock the OIDC token verifier with a stub that returns canned claims so
tests do not need a live Keycloak. The httpx async client is bound to the
FastAPI app via ASGI transport, so no real network is involved.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import cast
from uuid import UUID

import httpx
import jwt
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from verolas_auth import Role, TokenClaims, TokenVerifier

from verolas_api.main import create_app
from verolas_api.settings import Settings


@dataclass
class StubTokenVerifier:
    """Minimal stand in for the real TokenVerifier in tests.

    The `valid_tokens` mapping lets a test set up specific tokens that resolve
    to known claims. Anything else raises InvalidTokenError.
    """

    valid_tokens: dict[str, TokenClaims]

    def verify(self, token: str) -> TokenClaims:
        if token in self.valid_tokens:
            return self.valid_tokens[token]
        raise jwt.InvalidTokenError("Token is not in the stub verifier set.")


@pytest.fixture
def claims_owner() -> TokenClaims:
    return TokenClaims(
        keycloak_subject="kc-owner-1",
        email="owner@example.com",
        org_id=UUID("00000000-0000-4000-8000-00000000aa01"),
        roles=(Role.OWNER,),
        issued_at=0,
        expires_at=2_000_000_000,
    )


@pytest.fixture
def claims_viewer() -> TokenClaims:
    return TokenClaims(
        keycloak_subject="kc-viewer-1",
        email="viewer@example.com",
        org_id=UUID("00000000-0000-4000-8000-00000000aa01"),
        roles=(Role.VIEWER,),
        issued_at=0,
        expires_at=2_000_000_000,
    )


@pytest.fixture
def token_verifier(claims_owner: TokenClaims, claims_viewer: TokenClaims) -> StubTokenVerifier:
    return StubTokenVerifier(
        valid_tokens={
            "owner-token": claims_owner,
            "viewer-token": claims_viewer,
        }
    )


@pytest.fixture
def app(token_verifier: StubTokenVerifier) -> Iterator[FastAPI]:
    instance = create_app(
        settings=Settings(log_json=False, environment="test"),
        token_verifier=cast(TokenVerifier, token_verifier),
    )
    yield instance


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as ac:
            yield ac
