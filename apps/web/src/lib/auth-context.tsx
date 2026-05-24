"use client";

/**
 * Browser-side auth context.
 *
 * Owns the bearer token + identity in React state and mirrors it to
 * sessionStorage so a tab refresh keeps the user signed in. After the
 * token is loaded it fetches /v1/me so consumers know which org(s) the
 * user belongs to. The API client reads the token through
 * `setApiTokenGetter` so server-rendered code never sees it.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { meApi, setApiTokenGetter, type Me } from "./api";
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
  me: Me | null;
  isLoading: boolean;
  isLoadingMe: boolean;
  meError: string | null;
  signIn: (postLoginPath?: string) => Promise<void>;
  signOut: () => void;
  setTokens: (tokens: StoredTokens) => void;
  refreshMe: () => Promise<Me | null>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [tokens, setTokensState] = useState<StoredTokens | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMe, setIsLoadingMe] = useState(false);
  const [meError, setMeError] = useState<string | null>(null);
  const tokensRef = useRef<StoredTokens | null>(null);

  useEffect(() => {
    setTokensState(readTokens());
    setIsLoading(false);
  }, []);

  useEffect(() => {
    tokensRef.current = tokens;
    setApiTokenGetter(() => tokensRef.current?.accessToken ?? null);
  }, [tokens]);

  const refreshMe = useCallback(async (): Promise<Me | null> => {
    if (!tokensRef.current) {
      setMe(null);
      return null;
    }
    setIsLoadingMe(true);
    setMeError(null);
    try {
      const next = await meApi.get();
      setMe(next);
      return next;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setMeError(message);
      setMe(null);
      return null;
    } finally {
      setIsLoadingMe(false);
    }
  }, []);

  useEffect(() => {
    if (tokens) {
      void refreshMe();
    } else {
      setMe(null);
      setMeError(null);
    }
  }, [tokens, refreshMe]);

  const signIn = useCallback(async (postLoginPath?: string) => {
    if (postLoginPath) writePostLoginRedirect(postLoginPath);
    const url = await buildAuthorizationUrl();
    window.location.assign(url);
  }, []);

  const signOut = useCallback(() => {
    clearTokens();
    setTokensState(null);
    setMe(null);
    window.location.assign("/login");
  }, []);

  const setTokens = useCallback((next: StoredTokens) => {
    writeTokens(next);
    setTokensState(next);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      tokens,
      me,
      isLoading,
      isLoadingMe,
      meError,
      signIn,
      signOut,
      setTokens,
      refreshMe,
    }),
    [tokens, me, isLoading, isLoadingMe, meError, signIn, signOut, setTokens, refreshMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider.");
  return value;
}
