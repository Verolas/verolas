# ADR 007: Object storage, presigned uploads, ClamAV scanning, customer managed encryption keys

- Status: accepted
- Date: 2026-05-23
- Deciders: Shramish Kafle (founder, CEO)
- Consulted: ADR 002, ADR 004, ADR 005, ADR 006
- Informed: founding team

## Context

Every customer interaction with Verolas eventually drops a file: a DWG, an IFC, a PDF Statik, an XLSX BoQ, an XLSM with VBA. The platform needs durable storage, content addressable identity, versioning, virus scanning, and a customer managed encryption key (CMK) story for the high tier customers. The stack baseline pins this to Hetzner Object Storage plus a clamd pipeline. This ADR turns the bullets into a working implementation.

## Options considered

### Object backend: Hetzner Object Storage (chosen)

- Pros: EU sovereign, encrypted at rest by the provider, S3 compatible API so every S3 SDK works without modification, already in use for Terraform state and Postgres backups.
- Cons: smaller feature surface than AWS S3 (no native object lock, no CRR), per object access logs are limited.
- Reversibility: hybrid. Migration to a different S3 compatible provider is a bucket name and endpoint URL change.

### Direct upload path: presigned URLs (chosen)

- Pros: clients PUT directly to Object Storage. The API server never sees file bytes, so it stays small and fast. Multipart uploads use one presigned URL per part, completion is a single API call.
- Cons: the API must trust the metadata the client provides at upload start. Size, hash, and content type are verified after the object lands.

### Upload limits: 5 GB per file (chosen, matches the bible)

- Single shot for objects under roughly 100 MB. Multipart with 5 MiB to 5 GiB parts above that. Hard ceiling of 5 GB per object enforced in the API.

### Versioning: append only history with parent chain in Postgres (chosen)

- Every upload creates a new `files` row, optionally linked backward via `parent_file_id`. The S3 layer also has bucket versioning enabled, so the object bytes are recoverable even after a soft delete in the application. A view `files_latest` exposes the head of each chain for default listing.

### Virus scanning: ClamAV via clamd INSTREAM (chosen)

- Pros: open source, runs in cluster, well known signatures, free.
- Cons: catches around 95% of known malware; unknown payloads pass clean.
- Mitigation: macro bearing Office files (XLSM, DOCM, PPTM, etc.) are flagged at upload classification time and routed through the sandbox path in the firm knowledge ingestion workstream. ClamAV is the first gate, not the last.
- Implementation: the API streams the file from Object Storage through clamd over TCP. The verdict updates `files.status` and `files.scan_verdict` in a single transaction.

### Macro detection: filename and content type (chosen)

- The `verolas_storage.file_kinds.classify_file()` function looks at extension and content type. XLSM, XLTM, XLSB, DOCM, DOTM, PPTM, POTM, PPSM, XLAM, PPAM all flag `requires_macro_sandbox=True`. The flag persists into the database column `files.macro_sandbox_required` so downstream consumers (the firm knowledge ingestion pipeline once it lands) know which files need the sandboxed VBA analysis path.

### Customer managed encryption keys (CMK) architecture (designed, not yet implemented)

Three tiers:

1. **Platform managed encryption**. The default. Objects are encrypted at rest by Hetzner's server side encryption. The platform holds no key material; the customer trusts Hetzner plus Verolas.
2. **Verolas managed envelope encryption**. Each tenant gets a data encryption key (DEK), wrapped by a tenant key encryption key (KEK) stored in HashiCorp Vault (the Vault chart from ADR 002 stands up Vault, install pending). Object upload writes the wrapped DEK as metadata. The API decrypts on download. Rotating a KEK is a Vault operation; old objects keep their original wrapped DEK and re wrap on next access.
3. **Customer managed KEK**. The customer's KEK lives in their own HSM or KMS. Verolas asks the customer's KMS to unwrap the DEK at request time. The customer can revoke access at any time; once revoked, Verolas cannot read any object encrypted under that DEK. This tier requires SLA negotiation around the customer KMS latency budget and is reserved for the enterprise plan.

Today only tier 1 is active. The data model carries enough fields (`bucket`, `object_key`, future `kek_id`, future `wrapped_dek`) for tier 2 to slot in without a schema change. Tier 3 lands when an enterprise customer asks for it.

## Decision

| Bible bullet | Implementation |
| --- | --- |
| Hetzner Object Storage bucket(s) per environment | Created via S3 API: `verolas-files-dev` (nbg1, versioning on). Same pattern repeats for staging and prod. |
| File upload service: presigned URLs, multipart for large files up to 5 GB | `services/storage/verolas_storage/presigned.py` with single shot and multipart support. `apps/api/verolas_api/routes/v1/files.py` exposes `POST /v1/files` to request URLs. |
| File versioning model in PostgreSQL | Alembic migration `b2d4f6a8c0e2` creates the `files` table with parent chain, status enum, scan tracking, and the `files_latest` view. RLS scoped to `app.current_org_id`. |
| ClamAV virus scanning, macro flagging | `services/storage/verolas_storage/clamd.py` INSTREAM client. `infra/k8s/clamav/` Deployment, Service, PVC. Macro detection in `verolas_storage/file_kinds.py`. |
| Customer managed encryption keys (CMK) architecture | Three tier model documented in this ADR. Tier 1 active; tiers 2 and 3 land in follow up ADRs as the keys lifecycle (KEK generation, rotation, revocation) is fully specified. |

## Consequences

Positive:

- The API never sees file bytes. The TLS termination at Cloudflare plus Object Storage cuts a major attack surface and a major bandwidth cost.
- File metadata, versioning, and scan state are all in one Postgres table with RLS, so cross tenant leakage is impossible by construction.
- Macro bearing files are tagged at upload time, so the firm knowledge ingestion pipeline cannot accidentally treat an XLSM the same as an XLSX.
- ClamAV catches known threats. Macro sandbox catches the gap. Both are explicit, not magical.

Negative:

- ClamAV consumes roughly 1 GiB of RAM steady state. On the single node CX23 dev cluster this is the pod that finally tips the budget. Either we scale up the node before installing ClamAV, or we run ClamAV elsewhere (a separate small server) and point the cluster at it via DNS.
- Bucket creation is currently manual via the AWS CLI. The buckets become Terraform managed in a follow up so the IaC layer is the source of truth for them.
- CMK tiers 2 and 3 are designed but not implemented. Today the platform encryption story is "trust Hetzner".

New work created:

- Move bucket creation to Terraform (or OpenTofu) under `infra/modules/object-storage`.
- Install ClamAV on the cluster once the node has the headroom.
- Wire the database connection pool so the file upload routes can write rows; today they return 501 on the DB writes.
- Add a background worker that runs the scan after multipart complete and transitions `files.status` from `scanning` to `ready` or `quarantined`.
- ADR for CMK tier 2 implementation once Vault is installed and the wrapping ceremony is specified.
- ADR for CMK tier 3 enterprise customer integration pattern.

## Compliance and audit notes

- All buckets have versioning enabled. A malicious or accidental overwrite is recoverable for the retention window (Hetzner default is 30 days; we may extend).
- Server side encryption at rest is on by Hetzner default. Wire (TLS) encryption is enforced by the endpoint URL being HTTPS only.
- ClamAV verdicts and signatures are persisted on the `files` row, so an audit reviewer can answer "did we scan this file, what did the scanner say" from one query.
- Macro flagging persists on the row, so an audit reviewer can also answer "did this file go through the sandbox path".
- The S3 access keys in use are scoped to the matching bucket only. Per environment buckets plus per environment keys keep the blast radius bounded.

## Follow ups

1. Move the dev bucket creation into Terraform under `infra/modules/object-storage`; same for staging and prod when those clusters come up.
2. Install ClamAV after the cluster grows or after the API moves to a larger node.
3. Land the database connection pool in apps/api so the file routes can write rows.
4. Add the post upload scan worker, transitioning files from `scanning` to `ready` or `quarantined`.
5. ADR 008 for CMK tier 2 (Verolas managed envelope encryption via Vault).

## References

- Hetzner Object Storage: https://www.hetzner.com/storage/object-storage
- AWS S3 multipart upload: https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html
- ClamAV: https://www.clamav.net
- clamd protocol: https://docs.clamav.net/manual/Usage/Scanning.html#clamd
- Related: [[ADR 002]], [[ADR 004]], [[ADR 005]], [[ADR 006]]
