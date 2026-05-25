"""Version 1 routes for the Verolas API."""

from fastapi import APIRouter

from verolas_api.routes.v1 import (
    bridges,
    connector_oauth,
    connector_sync,
    connectors,
    files,
    library,
    me,
    onboarding,
    organizations,
    orgs,
    project_files,
    projects,
    runs,
    users,
)

api_v1 = APIRouter(prefix="/v1")
api_v1.include_router(me.router)
api_v1.include_router(onboarding.router)
api_v1.include_router(orgs.router)
api_v1.include_router(runs.router)
api_v1.include_router(runs.catalog_router)
api_v1.include_router(connectors.catalog_router)
api_v1.include_router(connectors.org_router)
api_v1.include_router(connectors.project_router)
api_v1.include_router(connector_oauth.oauth_router)
api_v1.include_router(connector_oauth.callback_router)
api_v1.include_router(connector_oauth.instance_router)
api_v1.include_router(connector_sync.router)
api_v1.include_router(bridges.admin_router)
api_v1.include_router(bridges.bridge_router)
api_v1.include_router(project_files.router)
api_v1.include_router(library.router)
api_v1.include_router(users.router)
api_v1.include_router(organizations.router)
api_v1.include_router(projects.router)
api_v1.include_router(files.router)
