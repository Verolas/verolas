"use client";

/**
 * Browser-side auth context.
 *
 * Holds the current bearer token + identity in React state and mirrors
 * it to sessionStorage so a tab refresh keeps the user signed in. The
 * API client reads the token through `setApiTokenGetter` so server-
 * rendered code never sees it.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { setApiTokenGetter } from "./api";
import { buildAuthorizationUrl } from "./oidc/client";
import {
  clearTokens,
  readTokens,
  writePostLoginRedirect,
  writeTokens,
  type StoredTokens,
} from "./oidc/session-storage";

interface AuthContextValue {
  tokens: StoredTokens | null;
  isLoading: boolean;
  signIn: (postLoginPath?: string) => Promise<void>;
  signOut: () => void;
  setTokens: (tokens: StoredTokens) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [tokens, setTokensState] = useState<StoredTokens | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setTokensState(readTokens());
    setIsLoading(false);
  }, []);

  useEffect(() => {
    setApiTokenGetter(() => tokens?.accessToken ?? null);
    return () => setApiTokenGetter(() => null);
  }, [tokens]);

  const signIn = useCallback(async (postLoginPath?: string) => {
    if (postLoginPath) writePostLoginRedirect(postLoginPath);
    const url = await buildAuthorizationUrl();
    window.location.assign(url);
  }, []);

  const signOut = useCallback(() => {
    clearTokens();
    setTokensState(null);
    window.location.assign("/login");
  }, []);

  const setTokens = useCallback((next: StoredTokens) => {
    writeTokens(next);
    setTokensState(next);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ tokens, isLoading, signIn, signOut, setTokens }),
    [tokens, isLoading, signIn, signOut, setTokens],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider.");
  return value;
}
