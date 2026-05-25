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
  syncBinding: (slug: string, projectId: string, bindingId: string) =>
    request<{
      files_added: number;
      files_updated: number;
      files_removed: number;
      bytes_pulled: number;
      notes: string[];
    }>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/connectors/bindings/${bindingId}/sync`,
      { method: "POST" },
    ),
  oauthStart: (slug: string, classId: string, redirectAfter: string) =>
    request<{ authorize_url: string; state: string }>(
      `/v1/orgs/${encodeURIComponent(slug)}/connectors/oauth/start`,
      {
        method: "POST",
        body: JSON.stringify({ class_id: classId, redirect_after: redirectAfter }),
      },
    ),
  listInstances: (slug: string, classId: string) =>
    request<{ ref: string; label: string; hint: string | null }[]>(
      `/v1/orgs/${encodeURIComponent(slug)}/connectors/${encodeURIComponent(classId)}/instances`,
    ),
};

export interface Bridge {
  id: string;
  org_id: string;
  name: string;
  status: "pending" | "active" | "offline" | "revoked";
  supported_tools: string[];
  hostname: string | null;
  agent_version: string | null;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface BridgeEnrollResult {
  bridge_id: string;
  name: string;
  token: string;
  api_base_url: string;
}

export const bridgesApi = {
  list: (slug: string) =>
    request<Bridge[]>(`/v1/orgs/${encodeURIComponent(slug)}/bridges`),
  enroll: (slug: string, name: string, supportedTools: string[]) =>
    request<BridgeEnrollResult>(`/v1/orgs/${encodeURIComponent(slug)}/bridges`, {
      method: "POST",
      body: JSON.stringify({ name, supported_tools: supportedTools }),
    }),
  revoke: (slug: string, bridgeId: string) =>
    request<void>(`/v1/orgs/${encodeURIComponent(slug)}/bridges/${bridgeId}`, {
      method: "DELETE",
    }),
};

export type ProjectFileKind =
  | "office_macro"
  | "office_plain"
  | "spreadsheet_plain"
  | "cad_drawing"
  | "cad_bim"
  | "pdf"
  | "image"
  | "archive"
  | "generic";

export interface ProjectFile {
  id: string;
  org_id: string;
  project_id: string | null;
  uploaded_by_user_id: string | null;
  filename: string;
  content_type: string | null;
  kind: ProjectFileKind;
  macro_sandbox_required: boolean;
  bucket: string;
  object_key: string;
  size_bytes: number | null;
  status: string;
  scan_verdict: string | null;
  created_at: string;
  updated_at: string;
}

export interface PresignedUpload {
  url: string;
  method: string;
  headers: Record<string, string>;
  expires_at: string;
}

export interface ProjectFileUploadResponse {
  file_id: string;
  object_key: string;
  bucket: string;
  kind: ProjectFileKind;
  macro_sandbox_required: boolean;
  single_part_upload: PresignedUpload | null;
  multipart_upload_id: string | null;
  multipart_part_urls: PresignedUpload[] | null;
}

export interface LibraryFolder {
  id: string;
  org_id: string;
  name: string;
  description: string | null;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
  file_count: number;
}

export interface LibraryFile {
  id: string;
  org_id: string;
  library_folder_id: string | null;
  uploaded_by_user_id: string | null;
  filename: string;
  content_type: string | null;
  kind: string;
  bucket: string;
  object_key: string;
  size_bytes: number | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface LibraryFileUploadResponse {
  file_id: string;
  object_key: string;
  bucket: string;
  kind: string;
  macro_sandbox_required: boolean;
  single_part_upload: PresignedUpload | null;
  multipart_upload_id: string | null;
  multipart_part_urls: PresignedUpload[] | null;
}

export const projectFilesApi = {
  list: (slug: string, projectId: string) =>
    request<ProjectFile[]>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/files/`,
    ),
  initiateUpload: (
    slug: string,
    projectId: string,
    body: {
      filename: string;
      content_type?: string | null;
      size_bytes: number;
      multipart_part_count?: number;
    },
  ) =>
    request<ProjectFileUploadResponse>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/files/`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
};

export const libraryApi = {
  listFolders: (slug: string) =>
    request<LibraryFolder[]>(`/v1/orgs/${encodeURIComponent(slug)}/library/folders`),
  createFolder: (slug: string, name: string, description?: string) =>
    request<LibraryFolder>(`/v1/orgs/${encodeURIComponent(slug)}/library/folders`, {
      method: "POST",
      body: JSON.stringify(description ? { name, description } : { name }),
    }),
  deleteFolder: (slug: string, folderId: string) =>
    request<void>(
      `/v1/orgs/${encodeURIComponent(slug)}/library/folders/${folderId}`,
      { method: "DELETE" },
    ),
  listFiles: (slug: string, folderId: string) =>
    request<LibraryFile[]>(
      `/v1/orgs/${encodeURIComponent(slug)}/library/folders/${folderId}/files`,
    ),
  uploadFile: (
    slug: string,
    folderId: string,
    body: { filename: string; content_type?: string | null; size_bytes: number },
  ) =>
    request<LibraryFileUploadResponse>(
      `/v1/orgs/${encodeURIComponent(slug)}/library/folders/${folderId}/files`,
      { method: "POST", body: JSON.stringify(body) },
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

// Workflow system (stage 1+2 backend).
//
// Mirrors the Pydantic schemas in apps/api/verolas_api/workflow/schema.py.
// Keep these types in sync with the API; the response shapes are stable
// across template versions because every run pins to one version.

export type WorkflowNodeKind =
  | "automated"
  | "gate.review"
  | "gate.approve"
  | "gate.signature"
  | "manual"
  | "external_wait"
  | "branch.condition"
  | "branch.iterate"
  | "submission"
  | "notification";

export type WorkflowNodeStatus =
  | "pending"
  | "ready"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "skipped";

export type WorkflowRunStatus =
  | "pending"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled";

export type WorkflowTemplateSource = "code" | "ui";

export interface WorkflowTemplate {
  id: string;
  org_id: string | null;
  slug: string;
  name: string;
  description: string | null;
  jurisdiction: string | null;
  project_type: string | null;
  source: WorkflowTemplateSource;
  active_version: number;
  active_version_id: string;
  node_count: number;
  is_global: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkflowRunNode {
  id: string;
  node_key: string;
  kind: WorkflowNodeKind;
  status: WorkflowNodeStatus;
  assignee_user_id: string | null;
  gate_decision: string | null;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  params: Record<string, unknown>;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface WorkflowRun {
  id: string;
  project_id: string;
  template_id: string | null;
  template_version_id: string | null;
  template_slug: string | null;
  template_name: string | null;
  document_id: string | null;
  document_name: string | null;
  display_name: string;
  status: WorkflowRunStatus;
  started_by_user_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  nodes: WorkflowRunNode[];
  created_at: string;
  updated_at: string;
}

export interface WorkflowGateDecision {
  decision: "approved" | "rejected";
  note?: string | null;
}

export interface WorkflowManualDone {
  outputs?: Record<string, unknown> | null;
}

export const workflowsApi = {
  listTemplates: (slug: string, jurisdiction?: string) => {
    const qs = jurisdiction
      ? `?jurisdiction=${encodeURIComponent(jurisdiction)}`
      : "";
    return request<WorkflowTemplate[]>(
      `/v1/orgs/${encodeURIComponent(slug)}/workflows/templates${qs}`,
    );
  },
  createRun: (slug: string, projectId: string, templateSlug: string) =>
    request<WorkflowRun>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/workflows/runs`,
      {
        method: "POST",
        body: JSON.stringify({ template_slug: templateSlug }),
      },
    ),
  listRuns: (slug: string, projectId: string, limit = 50) =>
    request<WorkflowRun[]>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/workflows/runs?limit=${limit}`,
    ),
  getRun: (slug: string, projectId: string, runId: string) =>
    request<WorkflowRun>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/workflows/runs/${runId}`,
    ),
  advanceGate: (
    slug: string,
    projectId: string,
    runId: string,
    nodeKey: string,
    decision: WorkflowGateDecision,
  ) =>
    request<WorkflowRun>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/workflows/runs/${runId}/nodes/${nodeKey}/advance`,
      {
        method: "POST",
        body: JSON.stringify({ gate: decision }),
      },
    ),
  advanceManual: (
    slug: string,
    projectId: string,
    runId: string,
    nodeKey: string,
    payload: WorkflowManualDone = {},
  ) =>
    request<WorkflowRun>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/workflows/runs/${runId}/nodes/${nodeKey}/advance`,
      {
        method: "POST",
        body: JSON.stringify({ manual: payload }),
      },
    ),
  cancelRun: (slug: string, projectId: string, runId: string) =>
    request<WorkflowRun>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/workflows/runs/${runId}/cancel`,
      { method: "POST" },
    ),
  // Get a short-lived presigned URL for a run artifact (e.g. floor
  // SVGs from the Origin floor_parse adapter, the sealed PDF, etc.).
  // The server validates that the storage_key belongs to this run.
  getArtifactUrl: (
    slug: string,
    projectId: string,
    runId: string,
    storageKey: string,
  ) => {
    const qs = `?storage_key=${encodeURIComponent(storageKey)}`;
    return request<WorkflowArtifactUrl>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/workflows/runs/${runId}/artifact${qs}`,
    );
  },
};

export interface WorkflowArtifactUrl {
  storage_key: string;
  url: string;
  method: string;
  expires_in: number;
}

// Per-floor SVG entry on the Origin floor_parse node's outputs.
export interface FloorSvgEntry {
  floor_key: string;
  name: string;
  is_roof: boolean;
  svg_key: string;
  size_bytes: number;
  svg_inline?: string;
}

// Workflow documents (stage 4 backend). A document is a project-scoped
// editable instance of a workflow graph. Runs can be created from a
// document (snapshotted) or from a template (legacy direct).

export interface WorkflowNode {
  key: string;
  kind: WorkflowNodeKind;
  name: string;
  description?: string | null;
  params: Record<string, unknown>;
  // Optional supernode membership. Nodes with the same group_key
  // render as one collapsible group card on the canvas. Missing on
  // older documents created before the group model landed.
  group_key?: string | null;
}

export interface WorkflowEdge {
  from_key: string;
  to_key: string;
  condition?: string | null;
}

export interface WorkflowGroup {
  key: string;
  name: string;
  description?: string | null;
  collapsed_by_default?: boolean;
  params?: Record<string, unknown>;
}

export interface WorkflowDefinition {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  entry_keys: string[];
  // Optional groups that bundle nodes into collapsible supernodes on
  // the canvas. Empty / missing means a flat graph.
  groups?: WorkflowGroup[];
}

export interface WorkflowDocument {
  id: string;
  org_id: string;
  project_id: string;
  folder: string;
  name: string;
  description: string | null;
  source_template_id: string | null;
  source_template_version_id: string | null;
  definition: WorkflowDefinition;
  node_count: number;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowDocumentCreate {
  name: string;
  folder?: string;
  description?: string | null;
  template_slug?: string | null;
}

export interface WorkflowDocumentUpdate {
  name?: string;
  folder?: string;
  description?: string | null;
  definition?: WorkflowDefinition;
}

export const workflowDocumentsApi = {
  create: (slug: string, projectId: string, body: WorkflowDocumentCreate) =>
    request<WorkflowDocument>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/workflows/documents`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  list: (slug: string, projectId: string) =>
    request<WorkflowDocument[]>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/workflows/documents`,
    ),
  get: (slug: string, projectId: string, documentId: string) =>
    request<WorkflowDocument>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/workflows/documents/${documentId}`,
    ),
  update: (
    slug: string,
    projectId: string,
    documentId: string,
    body: WorkflowDocumentUpdate,
  ) =>
    request<WorkflowDocument>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/workflows/documents/${documentId}`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),
  delete: (slug: string, projectId: string, documentId: string) =>
    request<void>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/workflows/documents/${documentId}`,
      { method: "DELETE" },
    ),
  createRunFromDocument: (
    slug: string,
    projectId: string,
    documentId: string,
  ) =>
    request<WorkflowRun>(
      `/v1/orgs/${encodeURIComponent(slug)}/projects/${projectId}/workflows/runs`,
      {
        method: "POST",
        body: JSON.stringify({ document_id: documentId }),
      },
    ),
};
