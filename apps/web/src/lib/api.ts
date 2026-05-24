/**
 * Thin client for the Verolas API.
 *
 * The bearer token is supplied by the auth context via `setApiTokenGetter`.
 * Calls return parsed JSON or throw `ApiError`. Server side rendering
 * sees no token; this client is expected to run in the browser.
 */

const BASE_URL =
  (typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_BASE_URL ?? "")
    : process.env.NEXT_PUBLIC_API_BASE_URL) ?? "https://api.dev.verolas.com";

type TokenGetter = () => string | null;

let tokenGetter: TokenGetter = () => null;

export function setApiTokenGetter(getter: TokenGetter): void {
  tokenGetter = getter;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  constructor(status: number, detail: string) {
    super(`API ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (init?.body) headers.set("Content-Type", "application/json");
  const token = tokenGetter();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  const text = await response.text();
  if (!response.ok) {
    let detail = text;
    try {
      detail = JSON.parse(text).detail ?? text;
    } catch {
      // keep raw text
    }
    throw new ApiError(response.status, detail);
  }
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

export type Discipline =
  | "structural"
  | "geotech"
  | "water"
  | "transport"
  | "review"
  | "practice";

export type ProjectStatus = "active" | "archived" | "deleted";

export interface Project {
  id: string;
  org_id: string;
  name: string;
  discipline: Discipline;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export const projectsApi = {
  list: () => request<Project[]>("/v1/projects/"),
  create: (name: string, discipline: Discipline) =>
    request<Project>("/v1/projects/", {
      method: "POST",
      body: JSON.stringify({ name, discipline }),
    }),
};
