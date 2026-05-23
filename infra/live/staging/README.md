# live/staging

Staging mirrors prod topology so that the prod cutover is boring.

Intentionally empty for now. The staging composition is added in a follow up PR once dev is healthy. When that PR lands, expect:

- Region `fsn1` (Falkenstein, prod region) so staging and prod share datacenter behaviour.
- Same node sizes as prod, scaled down by count.
- Delete protection on.
- Separate Hetzner project, separate Hetzner Object Storage bucket for state, separate Cloudflare token scope.
