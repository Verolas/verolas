/**
 * Thin client for the Verolas API.
 *
 * The bearer token is supplied by the auth context via `setApiTokenGetter`.
 * Calls return parsed JSON or throw `ApiError`. Server side rendering
 * sees no token; this client is expected to run in the browser.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.dev.verolas.com";

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
export type OrganizationStatus = "active" | "suspended" | "deleted";
export type MembershipRole =
  | "owner"
  | "admin"
  | "reviewer"
  | "engineer"
  | "viewer"
  | "auditor";

export interface Project {
  id: string;
  org_id: string;
  name: string;
  discipline: Discipline;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface MembershipSummary {
  organization_id: string;
  organization_slug: string;
  organization_name: string;
  organization_status: OrganizationStatus;
  organization_locale: string;
  organization_region: string;
  role: MembershipRole;
}

export interface Me {
  user_id: string | null;
  keycloak_subject: string;
  email: string | null;
  name: string | null;
  memberships: MembershipSummary[];
  locale_override: string | null;
  created_at: string | null;
}

export interface OnboardingPayload {
  organization_name: string;
  organization_slug?: string;
  primary_discipline: Discipline;
  first_project_name: string;
  full_name?: string;
  region: string;
  locale: string;
}

export interface OnboardingResult {
  user_id: string;
  organization_id: string;
  organization_slug: string;
  organization_name: string;
  organization_region: string;
  organization_locale: string;
  project_id: string;
  project_name: string;
  discipline: Discipline;
}

export type AgentRunStatus =
  | "queued"
  | "running"
  | "blocked"
  | "completed"
  | "failed"
  | "cancelled";
export type AgentRunTrigger = "manual" | "schedule" | "event";

export interface AgentRunPlanStep {
  label: string;
  status: string;
  detail?: string;
}

export interface AgentRun {
  id: string;
  project_id: string;
  org_id: string;
  agent_id: string;
  agent_name: string;
  tier: number;
  status: AgentRunStatus;
  trigger: AgentRunTrigger;
  triggered_by_user_id: string | null;
  brief: string;
  plan: AgentRunPlanStep[];
  current_step: number;
  progress_percent: number;
  result: Record<string, unknown>;
  cost_micro_usd: number;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentSummary {
  id: string;
  name: string;
  tier: number;
  blurb: string;
  region_tags: string[];
}

export const meApi = {
  get: () => request<Me>("/v1/me/"),
};

export const onboardingApi = {
  submit: (body: OnboardingPayload) =>
    request<OnboardingResult>("/v1/onboarding/", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

export const orgsApi = {
  listProjects: (slug: string) =>
    request<Project[]>(`/v1/orgs/${encodeURIComponent(slug)}/projects`),
  createProject: (slug: string, name: string, discipline: Discipline) =>
    request<Project>(`/v1/orgs/${encodeURIComponent(slug)}/projects`, {
      method: "POST",
      body: JSON.stringify({ name, discipline }),
    }),
  listAgents: (slug: string) =>
    request<AgentSummary[]>(`/v1/orgs/${encodeURIComponent(slug)}/agents/`),
};

export type ConnectorTier = "A" | "B" | "C" | "internal";
export type ConnectorAuthMethod =
  | "oauth2_pkce"
  | "oauth2_client_credentials"
  | "api_key"
  | "vendor_sdk"
  | "on_prem_agent"
  | "internal";
export type ConnectorCategory =
  | "cad_bim"
  | "structural_fea"
  | "geotech_fea"
  | "documents"
  | "construction_mgmt"
  | "markup"
  | "spreadsheets"
  | "communication"
  | "signing"
  | "internal";

export interface ConnectorClass {
  id: string;
  name: string;
  vendor: string;
  category: ConnectorCategory;
  tier: ConnectorTier;
  auth_method: ConnectorAuthMethod;
  blurb: string;
  region_tags: string[];
  scopes: string[];
  docs_url: string | null;
  instance_label: string;
}

export type ConnectorInstallStatus =
  | "pending"
  | "installed"
  | "error"
  | "uninstalled";

export interface ConnectorInstallation {
  id: string;
  org_id: string;
  class_id: string;
  status: ConnectorInstallStatus;
  installed_by_user_id: string | null;
  scopes: string[];
  oauth_account: Record<string, unknown>;
  last_sync_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export type ConnectorBindingStatus = "active" | "paused" | "error";

export interface ConnectorBinding {
  id: string;
  project_id: string;
  org_id: string;
  installation_id: string;
  class_id: string;
  instance_ref: string;
  instance_label: string;
  config: Record<string, unknown>;
  status: ConnectorBindingStatus;
  last_sync_at: string | null;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConnectorWaitlistEntry {
  id: string;
  org_id: string;
  class_id: string;
  requested_by_user_id: string | null;
  note: string | null;
  created_at: string;
}

export const connectorsApi = {
  catalog: () => request<ConnectorClass[]>("/v1/connectors/catalog"),
  listInstallations: (slug: string) =>
    request<ConnectorInstallation[]>(
      `/v1/orgs/${encodeURIComponent(slug)}/connectors/installations`,
    ),
  install: (slug: string, classId: string) =>
    request<ConnectorInstallation>(
      `/v1/orgs/${encodeURIComponent(slug)}/connectors/installations`,
      {
        method: "POST",
        body: JSON.stringify({ class_id: classId }),
      },
    ),
  uninstall: (slug: string, installationId: string) =>
    request<void>(
      `/v1/orgs/${encodeURIComponent(slug)}/connectors/installations/${installationId}`,
      { method: "DELETE" },
    ),
  waitlist: (slug: string, classId: string, note?: string) =>
    request<ConnectorWaitlistEntry>(
      `/v1/orgs/${encodeURIComponent(slug)}/connectors/waitlist`,
      {
        method: "POST",
        body: JSON.stringify(note ? { class_id: classId, note } : { class_id: classId }),
      },
    ),
  listBindings: (slug: string, projectId: string) =>
    request<ConnectorBinding[]>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/connectors/bindings`,
    ),
  bind: (
    slug: string,
    projectId: string,
    installationId: string,
    instanceRef: string,
    instanceLabel: string,
  ) =>
    request<ConnectorBinding>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/connectors/bindings`,
      {
        method: "POST",
        body: JSON.stringify({
          installation_id: installationId,
          instance_ref: instanceRef,
          instance_label: instanceLabel,
        }),
      },
    ),
  unbind: (slug: string, projectId: string, bindingId: string) =>
    request<void>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/connectors/bindings/${bindingId}`,
      { method: "DELETE" },
    ),
};

export const runsApi = {
  list: (slug: string, projectId: string) =>
    request<AgentRun[]>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/runs/`,
    ),
  get: (slug: string, projectId: string, runId: string) =>
    request<AgentRun>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/runs/${runId}`,
    ),
  create: (slug: string, projectId: string, agentId: string, brief: string) =>
    request<AgentRun>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/runs/`,
      {
        method: "POST",
        body: JSON.stringify({ agent_id: agentId, brief }),
      },
    ),
};
