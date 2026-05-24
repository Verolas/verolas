"""OAuth 2 PKCE configuration per Tier A connector class.

A `ConnectorOAuthConfig` is the static recipe for how to authenticate
against a vendor: the authorize endpoint, the token endpoint, and the
env vars holding the client_id / client_secret.

Per-class config is in code (not the DB) because it is bound to the
shipped catalog; rotating credentials at the platform level happens
via env vars and ConfigMap reloads, not via SQL.

Only Tier A connectors live here. Tier B (vendor SDK) and Tier C
(on-prem agent) follow different flows handled elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ConnectorOAuthConfig:
    """Static OAuth 2 PKCE recipe for one connector class.

    `extra_authorize_params` lets each vendor inject the niceties their
    OAuth dialect requires. Microsoft wants `prompt=consent` so re-installs
    refresh granted scopes; Google needs `access_type=offline` + the same
    prompt to mint a refresh_token; Autodesk only accepts
    `prompt=login|none|create` so we send `login`. Picking the right
    nudge per vendor avoids `invalid_request` 400s at the consent page.
    """

    class_id: str
    authorize_url: str
    token_url: str
    client_id_env: str
    client_secret_env: str
    audience: str | None = None
    extra_authorize_params: dict[str, str] = field(default_factory=dict)


OAUTH_CONFIGS: dict[str, ConnectorOAuthConfig] = {
    cfg.class_id: cfg
    for cfg in (
        ConnectorOAuthConfig(
            class_id="autodesk-aps",
            authorize_url="https://developer.api.autodesk.com/authentication/v2/authorize",
            token_url="https://developer.api.autodesk.com/authentication/v2/token",
            client_id_env="AUTODESK_APS_CLIENT_ID",
            client_secret_env="AUTODESK_APS_CLIENT_SECRET",
            extra_authorize_params={"prompt": "login"},
        ),
        ConnectorOAuthConfig(
            class_id="ms-sharepoint",
            authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
            client_id_env="MICROSOFT_GRAPH_CLIENT_ID",
            client_secret_env="MICROSOFT_GRAPH_CLIENT_SECRET",
            extra_authorize_params={"prompt": "consent"},
        ),
        ConnectorOAuthConfig(
            class_id="ms-onedrive",
            authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
            client_id_env="MICROSOFT_GRAPH_CLIENT_ID",
            client_secret_env="MICROSOFT_GRAPH_CLIENT_SECRET",
            extra_authorize_params={"prompt": "consent"},
        ),
        ConnectorOAuthConfig(
            class_id="ms-teams",
            authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
            client_id_env="MICROSOFT_GRAPH_CLIENT_ID",
            client_secret_env="MICROSOFT_GRAPH_CLIENT_SECRET",
            extra_authorize_params={"prompt": "consent"},
        ),
        ConnectorOAuthConfig(
            class_id="ms-outlook",
            authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
            client_id_env="MICROSOFT_GRAPH_CLIENT_ID",
            client_secret_env="MICROSOFT_GRAPH_CLIENT_SECRET",
            extra_authorize_params={"prompt": "consent"},
        ),
        ConnectorOAuthConfig(
            class_id="ms-excel",
            authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
            client_id_env="MICROSOFT_GRAPH_CLIENT_ID",
            client_secret_env="MICROSOFT_GRAPH_CLIENT_SECRET",
            extra_authorize_params={"prompt": "consent"},
        ),
        ConnectorOAuthConfig(
            class_id="google-drive",
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            client_id_env="GOOGLE_OAUTH_CLIENT_ID",
            client_secret_env="GOOGLE_OAUTH_CLIENT_SECRET",
            extra_authorize_params={"prompt": "consent", "access_type": "offline"},
        ),
        ConnectorOAuthConfig(
            class_id="google-sheets",
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            client_id_env="GOOGLE_OAUTH_CLIENT_ID",
            client_secret_env="GOOGLE_OAUTH_CLIENT_SECRET",
            extra_authorize_params={"prompt": "consent", "access_type": "offline"},
        ),
        ConnectorOAuthConfig(
            class_id="gmail",
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            client_id_env="GOOGLE_OAUTH_CLIENT_ID",
            client_secret_env="GOOGLE_OAUTH_CLIENT_SECRET",
            extra_authorize_params={"prompt": "consent", "access_type": "offline"},
        ),
        ConnectorOAuthConfig(
            class_id="slack",
            authorize_url="https://slack.com/oauth/v2/authorize",
            token_url="https://slack.com/api/oauth.v2.access",
            client_id_env="SLACK_CLIENT_ID",
            client_secret_env="SLACK_CLIENT_SECRET",
        ),
        ConnectorOAuthConfig(
            class_id="box",
            authorize_url="https://account.box.com/api/oauth2/authorize",
            token_url="https://api.box.com/oauth2/token",
            client_id_env="BOX_CLIENT_ID",
            client_secret_env="BOX_CLIENT_SECRET",
        ),
        ConnectorOAuthConfig(
            class_id="dropbox",
            authorize_url="https://www.dropbox.com/oauth2/authorize",
            token_url="https://api.dropboxapi.com/oauth2/token",
            client_id_env="DROPBOX_CLIENT_ID",
            client_secret_env="DROPBOX_CLIENT_SECRET",
        ),
        ConnectorOAuthConfig(
            class_id="egnyte",
            authorize_url="https://{tenant}.egnyte.com/puboauth/token",
            token_url="https://{tenant}.egnyte.com/puboauth/token",
            client_id_env="EGNYTE_CLIENT_ID",
            client_secret_env="EGNYTE_CLIENT_SECRET",
        ),
        ConnectorOAuthConfig(
            class_id="docusign",
            authorize_url="https://account-d.docusign.com/oauth/auth",
            token_url="https://account-d.docusign.com/oauth/token",
            client_id_env="DOCUSIGN_CLIENT_ID",
            client_secret_env="DOCUSIGN_CLIENT_SECRET",
        ),
        ConnectorOAuthConfig(
            class_id="adobe-sign",
            authorize_url="https://secure.adobesign.com/public/oauth/v2",
            token_url="https://secure.adobesign.com/oauth/v2/token",
            client_id_env="ADOBE_SIGN_CLIENT_ID",
            client_secret_env="ADOBE_SIGN_CLIENT_SECRET",
        ),
        ConnectorOAuthConfig(
            class_id="procore",
            authorize_url="https://login.procore.com/oauth/authorize",
            token_url="https://login.procore.com/oauth/token",
            client_id_env="PROCORE_CLIENT_ID",
            client_secret_env="PROCORE_CLIENT_SECRET",
        ),
        ConnectorOAuthConfig(
            class_id="bluebeam-studio",
            authorize_url="https://authentication.bluebeam.com/connect/authorize",
            token_url="https://authentication.bluebeam.com/connect/token",
            client_id_env="BLUEBEAM_CLIENT_ID",
            client_secret_env="BLUEBEAM_CLIENT_SECRET",
        ),
    )
}


def oauth_config(class_id: str) -> ConnectorOAuthConfig | None:
    """Look up the OAuth recipe for a connector class id."""
    return OAUTH_CONFIGS.get(class_id)


__all__ = ["OAUTH_CONFIGS", "ConnectorOAuthConfig", "oauth_config"]
