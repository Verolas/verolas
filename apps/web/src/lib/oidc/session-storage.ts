/**
 * sessionStorage-backed token + PKCE state storage.
 *
 * Bearer tokens live only for the lifetime of the browser tab. They are
 * never written to localStorage so an XSS on a different origin or a
 * leaked storage event cannot exfiltrate them across tabs. The PKCE
 * verifier and state are written before redirect to Keycloak and read
 * back in the callback handler.
 */

const TOKENS_KEY = "verolas_oidc_tokens";
const PKCE_KEY = "verolas_oidc_pkce";
const POST_LOGIN_KEY = "verolas_oidc_post_login";

export interface StoredTokens {
  accessToken: string;
  idToken: string;
  refreshToken: string | null;
  expiresAtMs: number;
  email: string | null;
  subject: string | null;
}

export interface PkceState {
  codeVerifier: string;
  state: string;
  nonce: string;
}

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

export function readTokens(): StoredTokens | null {
  if (!isBrowser()) return null;
  const raw = window.sessionStorage.getItem(TOKENS_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredTokens;
    if (parsed.expiresAtMs < Date.now()) {
      clearTokens();
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function writeTokens(tokens: StoredTokens): void {
  if (!isBrowser()) return;
  window.sessionStorage.setItem(TOKENS_KEY, JSON.stringify(tokens));
}

export function clearTokens(): void {
  if (!isBrowser()) return;
  window.sessionStorage.removeItem(TOKENS_KEY);
}

export function writePkce(pkce: PkceState): void {
  if (!isBrowser()) return;
  window.sessionStorage.setItem(PKCE_KEY, JSON.stringify(pkce));
}

export function readPkce(): PkceState | null {
  if (!isBrowser()) return null;
  const raw = window.sessionStorage.getItem(PKCE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PkceState;
  } catch {
    return null;
  }
}

export function clearPkce(): void {
  if (!isBrowser()) return;
  window.sessionStorage.removeItem(PKCE_KEY);
}

export function writePostLoginRedirect(path: string): void {
  if (!isBrowser()) return;
  window.sessionStorage.setItem(POST_LOGIN_KEY, path);
}

export function takePostLoginRedirect(): string | null {
  if (!isBrowser()) return null;
  const value = window.sessionStorage.getItem(POST_LOGIN_KEY);
  if (value) window.sessionStorage.removeItem(POST_LOGIN_KEY);
  return value;
}
