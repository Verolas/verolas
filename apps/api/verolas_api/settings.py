"""Runtime configuration loaded from environment variables.

Every field is required in production. Tests can override via the model
constructor or by setting environment variables in a pytest fixture.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from VEROLAS_API_* env vars."""

    model_config = SettingsConfigDict(env_prefix="VEROLAS_API_", env_file=None, extra="ignore")

    environment: str = Field(default="dev", description="dev, staging, prod")
    service_name: str = Field(default="verolas-api")
    log_level: str = Field(default="INFO", description="DEBUG, INFO, WARNING, ERROR, CRITICAL")
    log_json: bool = Field(default=True, description="Emit JSON logs in non dev environments")

    oidc_issuer: str = Field(
        default="http://localhost:8080/realms/verolas",
        description="OIDC issuer URL, e.g. https://auth.verolas.com/realms/verolas",
    )
    oidc_audience: str = Field(default="verolas-api", description="Expected aud claim")
    oidc_jwks_cache_ttl_seconds: int = Field(default=600, ge=60)

    database_url: str | None = Field(
        default=None,
        description="postgresql+psycopg://user:pass@host:5432/verolas. None disables DB routes.",
    )

    storage_endpoint_url: str | None = Field(
        default=None,
        description="Hetzner Object Storage endpoint, e.g. https://nbg1.your-objectstorage.com",
    )
    storage_region: str = Field(default="nbg1")
    storage_access_key_id: str = Field(default="")
    storage_secret_access_key: str = Field(default="")
    storage_bucket: str = Field(default="verolas-files-dev")
    storage_presign_expiry_seconds: int = Field(default=900, ge=60, le=7 * 24 * 3600)

    clamd_host: str | None = Field(
        default=None,
        description="ClamAV daemon host. None disables scan, leaving file status at scanning.",
    )
    clamd_port: int = Field(default=3310, ge=1, le=65535)
