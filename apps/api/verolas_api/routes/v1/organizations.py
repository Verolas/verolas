"""v1 organization routes. Skeleton only."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from verolas_api.dependencies import CurrentAuth
from verolas_api.middleware import sla_tier

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/")
@sla_tier(1)
async def list_organizations(auth: CurrentAuth) -> dict[str, str]:
    _ = auth
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Organization list is wired when the database connection lands.",
    )
