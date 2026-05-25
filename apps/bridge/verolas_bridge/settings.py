"""Bridge agent configuration, sourced from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BridgeSettings(BaseSettings):
    """Env-driven config for the bridge daemon.

    All values use the `VEROLAS_BRIDGE_` prefix so they don't collide
    with the api or web app when both are deployed in the same env.
    """

    model_config = SettingsConfigDict(
        env_prefix="VEROLAS_BRIDGE_",
        env_file=None,
        extra="ignore",
    )

    token: str = Field(
        description="The vbk_<id>_<secret> token issued at enrollment.",
    )
    api_base_url: str = Field(
        default="https://api.dev.verolas.com",
        description="Verolas cloud root, e.g. https://api.dev.verolas.com",
    )
    poll_interval_seconds: float = Field(
        default=10.0,
        ge=1.0,
        le=600.0,
        description="Delay between successive polls when no jobs are returned.",
    )
    hostname: str | None = Field(
        default=None,
        description="Optional hostname stamp surfaced on the bridge admin page.",
    )
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=False)
