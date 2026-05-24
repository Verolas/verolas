/**
 * oauth4webapi wrappers for the PKCE authorization code flow.
 *
 * Discovery resolves the realm's well-known config once per session
 * and is cached on the module. The auth code exchange returns parsed
 * tokens including expiry so the session storage layer can drop them
 * automatically.
 */

import * as oauth from "oauth4webapi";

import { oidcConfig, redirectUri } from "./config";
import {
  clearPkce,
  readPkce,
  writePkce,
  type StoredTokens,
} from "./session-storage";

let cachedAuthServer: oauth.AuthorizationServer | null = null;

async function discover(): Promise<oauth.AuthorizationServer> {
  if (cachedAuthServer) return cachedAuthServer;
  const config = oidcConfig();
  const issuerUrl = new URL(config.issuer);
  const response = await oauth.discoveryRequest(issuerUrl, { algorithm: "oidc" });
  cachedAuthServer = await oauth.processDiscoveryResponse(issuerUrl, response);
  return cachedAuthServer;
}

export async function buildAuthorizationUrl(): Promise<string> {
  const config = oidcConfig();
  const authServer = await discover();
  if (!authServer.authorization_endpoint) {
    throw new Error("OIDC issuer is missing the authorization_endpoint.");
  }

  const codeVerifier = oauth.generateRandomCodeVerifier();
  const codeChallenge = await oauth.calculatePKCECodeChallenge(codeVerifier);
  const state = oauth.generateRandomState();
  const nonce = oauth.generateRandomNonce();

  writePkce({ codeVerifier, state, nonce });

  const url = new URL(authServer.authorization_endpoint);
  url.searchParams.set("client_id", config.clientId);
  url.searchParams.set("redirect_uri", redirectUri());
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", config.scope);
  url.searchParams.set("code_challenge", codeChallenge);
  url.searchParams.set("code_challenge_method", "S256");
  url.searchParams.set("state", state);
  url.searchParams.set("nonce", nonce);
  return url.toString();
}

export async function handleCallback(searchParams: URLSearchParams): Promise<StoredTokens> {
  const config = oidcConfig();
  const authServer = await discover();
  const client: oauth.Client = { client_id: config.clientId };
  const pkce = readPkce();
  if (!pkce) {
    throw new Error("Missing PKCE state. Restart sign in from /login.");
  }

  const validated = oauth.validateAuthResponse(authServer, client, searchParams, pkce.state);

  const response = await oauth.authorizationCodeGrantRequest(
    authServer,
    client,
    oauth.None(),
    validated,
    redirectUri(),
    pkce.codeVerifier,
  );

  const result = await oauth.processAuthorizationCodeResponse(authServer, client, response, {
    expectedNonce: pkce.nonce,
    requireIdToken: true,
  });

  clearPkce();

  const claims = oauth.getValidatedIdTokenClaims(result);
  if (!claims) {
    throw new Error("Token response did not include an ID token.");
  }
  const accessToken = result.access_token;
  const idToken = result.id_token ?? "";
  const refreshToken = result.refresh_token ?? null;
  const expiresInSeconds = typeof result.expires_in === "number" ? result.expires_in : 300;
  const expiresAtMs = Date.now() + expiresInSeconds * 1000;

  const email = typeof claims.email === "string" ? claims.email : null;
  const subject = typeof claims.sub === "string" ? claims.sub : null;

  return { accessToken, idToken, refreshToken, expiresAtMs, email, subject };
}
