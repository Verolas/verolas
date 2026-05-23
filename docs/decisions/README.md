# Architecture Decision Records

This directory holds the immutable record of significant architecture and engineering decisions for Verolas. Each ADR is a Markdown file, numbered sequentially.

- Start a new ADR by copying `000-template.md` to `NNN-short-slug.md` where `NNN` is the next number.
- Set `Status` to `proposed` until merged, then move to `accepted`.
- Never edit an accepted ADR. Supersede it with a new ADR and update the old one's status to `superseded by ADR XXX`.
- ADRs are required for any decision that locks in a long lived choice (framework, vendor, sovereignty boundary, agent topology, eval methodology, regulatory posture).

Numbered index:

- ADR 000: Template (not a decision, scaffolding only)
- ADR 001: Monorepo layout and stack baseline
- ADR 002: Infrastructure baseline (Hetzner, kube-hetzner, OpenTofu, Cloudflare)
- ADR 003: CI/CD foundation, GitHub Actions on hosted runners, pre commit hooks
