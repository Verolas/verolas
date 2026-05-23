"""Version 1 routes for the Verolas API."""

from fastapi import APIRouter

from verolas_api.routes.v1 import files, organizations, projects, users

api_v1 = APIRouter(prefix="/v1")
api_v1.include_router(users.router)
api_v1.include_router(organizations.router)
api_v1.include_router(projects.router)
api_v1.include_router(files.router)
