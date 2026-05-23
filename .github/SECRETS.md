# Repository secrets required by CI

These secrets are read by workflows under `.github/workflows/`. Configure them at GitHub repo Settings, Secrets and variables, Actions.

## Image pipeline (`image.yml`)

No secrets needed. `GITHUB_TOKEN` is provided automatically and is used to push images to `ghcr.io` and to sign with Cosign keyless via OIDC. Trivy SARIF upload uses the same token.

## IaC plan on PR (`iac-plan.yml`)

| Secret name | Purpose | Where to get it |
| --- | --- | --- |
| `HCLOUD_TOKEN` | Hetzner Cloud API token, Read and Write on the dev project | Hetzner dashboard, Security, API Tokens |
| `HETZNER_S3_ACCESS_KEY` | S3 backend access key for the dev state bucket | Hetzner Object Storage, Manage Credentials |
| `HETZNER_S3_SECRET_KEY` | S3 backend secret key | Same as above |
| `CLOUDFLARE_API_TOKEN` | Zone DNS Edit on `verolas.com` | Cloudflare My Profile, API Tokens |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID | Cloudflare dashboard, right sidebar |
| `SSH_PUBLIC_KEY` | Contents of `~/.ssh/verolas_cluster_dev.pub` | From your workstation |
| `SSH_PRIVATE_KEY` | Contents of `~/.ssh/verolas_cluster_dev` | From your workstation |

The SSH key contents are needed because the kube-hetzner module reads them via `file()` at plan time, even though apply happens locally for now.

For staging and prod, add separately scoped tokens once those environments exist. The workflow auto-detects which environment a PR changes and runs the matching plan.

## Other workflows

`ci.yml`, `iac.yml`, `pr-meta.yml`, `test-python.yml`, `test-rust.yml`, `test-e2e.yml` do not need any secrets.
