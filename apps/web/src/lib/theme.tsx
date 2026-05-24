"use client";

/**
 * Theme provider with light + dark support.
 *
 * The active theme lives on the <html> element as data-theme. The
 * provider reads localStorage on mount and falls back to system
 * preference if nothing has been chosen yet. To avoid a flash of
 * light theme before hydration the root layout includes a small
 * inline script that sets the attribute before React mounts.
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

export type Theme = "light" | "dark";
export type ThemeChoice = Theme | "system";

const STORAGE_KEY = "verolas_theme";

interface ThemeContextValue {
  theme: Theme;
  choice: ThemeChoice;
  setChoice: (choice: ThemeChoice) => void;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readChoice(): ThemeChoice {
  if (typeof window === "undefined") return "system";
  const value = window.localStorage.getItem(STORAGE_KEY);
  if (value === "light" || value === "dark" || value === "system") return value;
  return "system";
}

function resolve(choice: ThemeChoice): Theme {
  if (choice !== "system") return choice;
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function apply(theme: Theme): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = theme;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>("system");
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const c = readChoice();
    setChoiceState(c);
    const t = resolve(c);
    setTheme(t);
    apply(t);
  }, []);

  useEffect(() => {
    if (choice !== "system") return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event: MediaQueryListEvent): void => {
      const t: Theme = event.matches ? "dark" : "light";
      setTheme(t);
      apply(t);
    };
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [choice]);

  const setChoice = useCallback((next: ThemeChoice) => {
    setChoiceState(next);
    if (next === "system") {
      window.localStorage.removeItem(STORAGE_KEY);
    } else {
      window.localStorage.setItem(STORAGE_KEY, next);
    }
    const t = resolve(next);
    setTheme(t);
    apply(t);
  }, []);

  const toggle = useCallback(() => {
    setChoice(theme === "dark" ? "light" : "dark");
  }, [setChoice, theme]);

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, choice, setChoice, toggle }),
    [theme, choice, setChoice, toggle],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used inside ThemeProvider.");
  return value;
}

/**
 * Inline script that runs before React hydrates. Reads localStorage +
 * system preference, applies the theme to <html>. Avoids the FOIT
 * flash where the page renders in light and switches to dark on mount.
 */
export const themeBootstrapScript = `(() => {
  try {
    var choice = localStorage.getItem('${STORAGE_KEY}');
    var theme = choice;
    if (theme !== 'light' && theme !== 'dark') {
      theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    document.documentElement.dataset.theme = theme;
  } catch (_) {}
})();`;
