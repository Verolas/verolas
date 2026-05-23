"""Verolas authentication primitives.

This package collects everything every Python service needs to enforce auth:
OIDC token verification, RBAC role definitions and checks, TOTP MFA helpers,
and the tenant scoping context that pairs with the database row level
security policies.
"""

from verolas_auth.mfa import MfaProvisioning, generate_totp_secret, verify_totp_code
from verolas_auth.roles import Role, role_at_least
from verolas_auth.tenancy import TenancyContext, sql_set_tenancy
from verolas_auth.tokens import TokenClaims, TokenVerifier, TokenVerifierSettings

__all__ = [
    "MfaProvisioning",
    "Role",
    "TenancyContext",
    "TokenClaims",
    "TokenVerifier",
    "TokenVerifierSettings",
    "generate_totp_secret",
    "role_at_least",
    "sql_set_tenancy",
    "verify_totp_code",
]
__version__ = "0.0.0"
