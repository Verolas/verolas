## ADR 009: Project workspace data model, audit log Merkle chain, project CRUD wired end to end

- Status: accepted
- Date: 2026-05-24
- Deciders: Shramish Kafle (founder, CEO)
- Consulted: ADR 004, ADR 005, ADR 006
- Informed: founding team

## Context

Phase 8 needs the project lifecycle data model, working CRUD against it, file association to projects, and an append only audit log. The audit log must be tamper evident; the bible specifies it as Merkle chained. This ADR pins the schema, the chaining mechanism, the application path that drives it, and the trade offs we accepted to ship the dev cluster wiring today.

## Options considered

### Audit log chain mechanism: BEFORE INSERT trigger in Postgres (chosen)

- Pros: the trigger computes prev_hash, this_hash, and seq inside a single transactional step holding a row lock on the per org tail row. The application cannot accidentally write inconsistent rows: any path that talks to the database goes through the trigger. Verification walks (audit reviewer) read the chain forward, recomputing each hash, and rely on Postgres's existing guarantees rather than application correctness.
- Cons: serialises append throughput to one row per org per round trip. Acceptable: audit events are low volume and fan out by org.
- Implementation detail: the trigger uses pgcrypto's digest function with sha256; pgcrypto is already installed.

Alternatives:

- Application managed chain: every insert path computes prev_hash by SELECTing the latest row, then inserting. Race risk under concurrent writes; requires SERIALIZABLE or explicit row locking in every caller. Easy to get wrong.
- Hash chain in a separate process (Merkle service): higher latency, more moving parts, no real audit benefit at this scale.
- Tamper proof external log (CockroachDB CDC into an immutable log service): right answer for prod, premature for dev.

### Per request transaction with tenancy set then yield connection (chosen)

- Each API request opens a transaction via the psycopg async pool, sets `app.current_user_id` and `app.current_org_id` (the RLS policies read these), and hands the connection to the route handler. Commit on success, rollback on exception.
- The activity log write happens in the same transaction as the resource write. If the project insert fails for any reason, the audit entry rolls back too. We never want an audit row without a backing change, or a change without an audit row.

### Project ↔ workspace shape (chosen)

- A project has at least one workspace. Today every project gets a default workspace lazily on first file upload. Multi workspace per project is the path for parallel design variants and will land when teams need it.
- Workspaces carry org_id explicitly (denormalised through project) so the RLS policy is a one column equality check rather than a join. The denormalisation is enforced by the route layer; a future trigger can enforce it on the database.

### Files now link to a project and workspace (chosen)

- The files table from the object storage workstream grows two nullable columns: project_id and workspace_id. Existing files (none in production, by definition) stay nullable. New uploads from the file upload UI carry the project association.

### Frontend project list and create form (chosen, half delivered today)

- The new `ProjectsPanel` client component fetches `/v1/projects/` on mount, lists the projects, and posts a new one via `/v1/projects/`. On auth failure the panel renders a "Sign in" hint instead of an opaque error. The OIDC PKCE token acquisition is the next workstream; today the client looks for a bearer token in `localStorage` so a developer can paste one in to drive the API end to end manually.

### Phase 8 deferred items

- **File upload UI inside a project workspace.** The presigned URL machinery exists (the object storage workstream), the file ↔ project link exists (this phase), and the front end will get a file picker in a follow up. The audit log entry pattern for uploads is the same as for project creates; no new chain work needed.
- **OIDC PKCE on the front end.** The `/login` page is still a static skeleton. Until that lands, the API enforces auth but the front end cannot acquire a token automatically; manual injection works for development.

## Decision

| Bible bullet | Implementation |
| --- | --- |
| Project, Workspace, File, Membership, ActivityLog tables | Alembic revision `c3e5f7b9d1f3` adds projects, workspaces, activity_log; files (the object storage workstream) gains project_id and workspace_id; memberships exists from the auth workstream. |
| API endpoints CRUD on projects | `apps/api/verolas_api/routes/v1/projects.py` exposes list, get, create with RLS aware transactions. PATCH and DELETE come in a follow up. |
| Frontend project creation flow + project list | `apps/web/src/components/projects-panel.tsx` (client component) hits the API and renders states for loading, error, empty, and populated. |
| File upload UI in project workspace | Deferred; presigned URL service is already production ready from the object storage workstream. |
| Audit log infrastructure: append only, Merkle chained | `app.activity_log_chain` BEFORE INSERT trigger computes prev_hash, this_hash, and seq, takes a per org row lock to serialise concurrent inserts. UPDATE and DELETE blocked by RLS policy that always evaluates false. `audit.record_activity` helper at `apps/api/verolas_api/audit.py` is the only writer in application code. |

## Consequences

Positive:

- Audit log tampering breaks the chain at verification time. Any deleted row leaves a gap in seq; any modified row produces a hash that no longer matches the next row's prev_hash. Trivial to verify with a single forward walk.
- Project writes and their audit entries are atomic. No "ghost project" or "ghost audit" rows.
- The application layer cannot write the audit row's hash incorrectly; the trigger is the source of truth.
- RLS still scopes everything by org. Even an audit log SELECT cannot leak across orgs.

Negative:

- Audit log throughput is one row per org per round trip. Fine at our scale. If a single org generates thousands of events per second in the future, we partition the chain or move to a streaming log.
- Concurrent updates to the same project from two requests can interleave in surprising ways without per resource locking. Acceptable for projects since they have one owner; will need attention for high contention resources later.

## Compliance and audit notes

- The Merkle chain plus the append only RLS policy together satisfy the audit trail integrity expectation in the EU AI Act high risk record keeping regime. The recovery time for "show me everything user X did in org Y in March" is one indexed query.
- The chain anchor (zero hash for the first row of each org) is a fixed constant. We do not externalise the chain head today; in production we will periodically anchor the chain head into a write only external store (e.g., a Cloudflare R2 bucket with object lock) so a malicious operator with database access cannot also tamper with the external anchor.

## Follow ups

1. PATCH and DELETE for projects with audit log entries.
2. POST /v1/projects/{id}/files that wires the upload flow end to end (project association + file row + audit row).
3. OIDC PKCE on the front end so the panel acquires a token without manual injection.
4. Periodic external anchor of the per org chain head for tamper resistance against operator level adversaries.
5. A scheduled audit verifier Job that walks the chain per org and emits a metric on any inconsistency.

## References

- pgcrypto digest function: https://www.postgresql.org/docs/current/pgcrypto.html
- Merkle tree primer: https://en.wikipedia.org/wiki/Merkle_tree
- Related: [[ADR 004]], [[ADR 005]], [[ADR 006]]
