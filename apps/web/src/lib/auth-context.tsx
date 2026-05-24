"use client";

/**
 * Browser-side auth context.
 *
 * Owns the bearer token + identity in React state and mirrors it to
 * sessionStorage so a tab refresh keeps the user signed in. After the
 * token is loaded it fetches /v1/me so consumers know which org(s) the
 * user belongs to. The API client reads the token through
 * `setApiTokenGetter` so server-rendered code never sees it.
 *
 * `meStatus` is the source of truth for "have we heard back from
 * /v1/me yet"; the loading flag flips true the moment the token is
 * read so ProtectedRoute never redirects in the gap between
 * sessionStorage hydration and the first API response.
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

export type MeStatus = "idle" | "loading" | "loaded" | "error";

interface AuthContextValue {
  tokens: StoredTokens | null;
  me: Me | null;
  isLoading: boolean;
  meStatus: MeStatus;
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
  const [meStatus, setMeStatus] = useState<MeStatus>("idle");
  const [meError, setMeError] = useState<string | null>(null);
  const tokensRef = useRef<StoredTokens | null>(null);

  useEffect(() => {
    const initial = readTokens();
    setTokensState(initial);
    // Flip meStatus optimistically so ProtectedRoute knows /v1/me is
    // about to load and does not redirect in the gap before the
    // refreshMe effect fires.
    if (initial) setMeStatus("loading");
    setIsLoading(false);
  }, []);

  useEffect(() => {
    tokensRef.current = tokens;
    setApiTokenGetter(() => tokensRef.current?.accessToken ?? null);
  }, [tokens]);

  const refreshMe = useCallback(async (): Promise<Me | null> => {
    if (!tokensRef.current) {
      setMe(null);
      setMeStatus("idle");
      return null;
    }
    setMeStatus("loading");
    setMeError(null);
    try {
      const next = await meApi.get();
      setMe(next);
      setMeStatus("loaded");
      return next;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setMeError(message);
      setMe(null);
      setMeStatus("error");
      return null;
    }
  }, []);

  useEffect(() => {
    if (tokens) {
      void refreshMe();
    } else {
      setMe(null);
      setMeStatus("idle");
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
    setMeStatus("idle");
    window.location.assign("/login");
  }, []);

  const setTokens = useCallback((next: StoredTokens) => {
    writeTokens(next);
    setMeStatus("loading");
    setTokensState(next);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      tokens,
      me,
      isLoading,
      meStatus,
      meError,
      signIn,
      signOut,
      setTokens,
      refreshMe,
    }),
    [tokens, me, isLoading, meStatus, meError, signIn, signOut, setTokens, refreshMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider.");
  return value;
}
