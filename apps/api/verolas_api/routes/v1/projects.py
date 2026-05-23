"""v1 project routes. Skeleton only."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from verolas_api.dependencies import CurrentAuth
from verolas_api.middleware import sla_tier

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/")
@sla_tier(1)
async def list_projects(auth: CurrentAuth) -> dict[str, str]:
    _ = auth
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Project list is wired when the database connection lands.",
    )
