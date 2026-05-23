"""v1 user routes. Skeleton only; persistence lands when the DB plumbing arrives."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from verolas_api.dependencies import CurrentAuth
from verolas_api.middleware import sla_tier
from verolas_api.schemas import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
@sla_tier(1)
async def me(auth: CurrentAuth) -> UserOut:
    """Return the calling user's profile.

    Skeleton: the verifier identifies the user, but the database lookup that
    resolves the Keycloak subject to a `users` row is not wired yet. Returns
    a 501 until the DB workstream comes online.
    """
    _ = auth
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="User lookup is wired when the database connection lands.",
    )
