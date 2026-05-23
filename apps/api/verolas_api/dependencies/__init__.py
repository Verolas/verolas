"""FastAPI dependency factories."""

from verolas_api.dependencies.auth import (
    AuthContext,
    CurrentAuth,
    require_auth,
    require_role,
)

__all__ = ["AuthContext", "CurrentAuth", "require_auth", "require_role"]
