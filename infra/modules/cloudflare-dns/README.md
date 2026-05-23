# Cloudflare DNS module

Manages DNS records inside an existing Cloudflare zone.

## Records created

| Record | Type | Purpose |
| ------ | ---- | ------- |
| `@` | A | Apex, points at the marketing site IP. Opt in via `create_apex`. |
| `www` | CNAME | Maps www to apex. Opt in via `create_www`. |
| `<env>` | A | Cluster ingress for this environment (dev, staging, prod). |
| `*.<env>` | CNAME | Wildcard for cluster services. Opt out via `create_wildcard_env_subdomain = false`. |
| `@` CAA | CAA | Restricts certificate issuance to Let's Encrypt. |

## Bootstrap order

The zone itself is not created here. Register the domain at your registrar, point its nameservers at Cloudflare, and confirm the zone is Active in the Cloudflare dashboard before applying this module.

## Regional ccTLDs

`verolas.de`, `verolas.at`, `verolas.ch` and any future ccTLDs follow the same pattern. Each gets its own zone in Cloudflare and a separate invocation of this module.
