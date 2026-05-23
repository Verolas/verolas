# live/prod

Production. EU sovereign, Hetzner Falkenstein.

Intentionally empty for now. The prod composition lands once dev is healthy, staging mirrors prod cleanly, and at least one customer pilot is in flight. When that PR lands, expect:

- Region `fsn1` (Falkenstein, Germany)
- Larger node sizes, more workers, multi-AZ aware placement
- Delete protection on every resource
- Separate Hetzner project, separate Object Storage bucket for state, separate Cloudflare token scope
- Apply gated to a controlled runner with mTLS to Vault
- Mandatory plan review by two reviewers per ADR 002

Production never runs `tofu destroy`. Decommissioning is an ADR backed event.
