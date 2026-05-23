"""Auth dependencies for FastAPI routes.

`require_auth` verifies the bearer token using the shared verolas_auth library
and returns the parsed claims. `require_role(role)` builds a dependency that
also checks the caller has at least the given role on the active org.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from verolas_auth import Role, TokenClaims, TokenVerifier, role_at_least


@dataclass(frozen=True, slots=True)
class AuthContext:
    """The verified claims for an authenticated request."""

    claims: TokenClaims


_bearer = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def _verifier_from_request(request: Request) -> TokenVerifier:
    verifier: TokenVerifier | None = getattr(request.app.state, "token_verifier", None)
    if verifier is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token verifier is not configured on the app.",
        )
    return verifier


async def require_auth(request: Request, credentials: BearerCredentials) -> AuthContext:
    """Verify the Authorization header and return parsed claims."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    verifier = _verifier_from_request(request)
    try:
        claims = verifier.verify(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc) or "Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return AuthContext(claims=claims)


CurrentAuth = Annotated[AuthContext, Depends(require_auth)]


def require_role(role: Role) -> object:
    """Return a dependency that enforces the caller has at least `role`."""

    async def _dep(auth: CurrentAuth) -> AuthContext:
        if not any(role_at_least(actual, role) for actual in auth.claims.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role.value}' or higher required.",
            )
        return auth

    return _dep
