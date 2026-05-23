# Preflight: before you run `tofu apply`

Every item in this list must be complete before `tofu apply` will succeed in any environment. Work through it top to bottom.

## 1. Accounts and billing

- [ ] Hetzner Cloud account exists at https://accounts.hetzner.com. Billing method on file. Verified email.
- [ ] Hetzner Cloud "project" created per environment: `verolas-dev`, `verolas-staging`, `verolas-prod`. Each project is a hard isolation boundary in Hetzner Cloud.
- [ ] Hetzner Object Storage activated. Bucket region: `fsn1` (Falkenstein, Germany) for prod, `nbg1` (Nuremberg, Germany) for staging, either for dev.
- [ ] Cloudflare account exists, billing method on file.
- [ ] Domain `verolas.com` registered. Verify in `whois` that the registrar lock is on and WHOIS privacy is enabled.
- [ ] Domain `verolas.com` nameservers pointed at Cloudflare. Cloudflare dashboard should show the zone as Active.
- [ ] Regional ccTLDs reserved (parked, not yet active): `verolas.de`, `verolas.at`, `verolas.ch`, plus any others for waves beyond DACH.

## 2. API tokens

Generate read-write tokens with the minimum scopes needed. Drop them into the environment's `terraform.tfvars` file. That file is gitignored.

- [ ] **Hetzner Cloud API token** per project. Dashboard, project, Security, API Tokens. Permissions: Read & Write.
- [ ] **Hetzner Object Storage credentials** per environment. Dashboard, Object Storage, Manage Credentials. Generate access key + secret key.
- [ ] **Cloudflare API token** scoped to `Zone.DNS:Edit`, `Zone.Zone:Read`, and `Account.Cloudflare Tunnel:Edit` (the last only when Tunnel is in use). Include only the `verolas.com` zone in the token scope for now.
- [ ] **Cloudflare account ID** captured. It is shown on the Cloudflare dashboard right rail.

Drop them into `infra/live/<env>/terraform.tfvars`:

```hcl
hcloud_token         = "<hetzner-cloud-token>"
hetzner_s3_access_key = "<object-storage-access-key>"
hetzner_s3_secret_key = "<object-storage-secret-key>"
cloudflare_api_token = "<cloudflare-token>"
cloudflare_account_id = "<cloudflare-account-id>"
```

Never commit this file.

## 3. SSH keys

- [ ] Generate a per environment SSH key pair (ed25519). Store the private key in your password manager. Add the public key to each Hetzner Cloud project, named `verolas-<env>-bootstrap`.
- [ ] Add your own personal SSH public key to each Hetzner Cloud project for emergency access, named `<initials>-personal`.

The kube-hetzner bootstrap reads SSH keys directly from the Hetzner project, so they must exist before `tofu apply`.

## 4. Local tooling

Install these once:

- [ ] [OpenTofu](https://opentofu.org/docs/intro/install/) 1.8 or newer (`brew install opentofu` on macOS)
- [ ] [kubectl](https://kubernetes.io/docs/tasks/tools/) 1.31 or newer
- [ ] [Helm](https://helm.sh/docs/intro/install/) 3.16 or newer
- [ ] [hcloud CLI](https://github.com/hetznercloud/cli) for inspection
- [ ] [k9s](https://k9scli.io) for cluster ergonomics, optional but recommended

Verify everything:

```bash
tofu version
kubectl version --client
helm version --short
hcloud version
```

## 5. State backend bootstrap

Hetzner Object Storage holds Terraform state. The bucket itself is created out of band so we never have a chicken-and-egg.

- [ ] Manually create three buckets via the Hetzner Cloud console:
  - `verolas-tfstate-dev` (`nbg1` or `fsn1`)
  - `verolas-tfstate-staging` (`fsn1`)
  - `verolas-tfstate-prod` (`fsn1`)
- [ ] On each bucket, enable versioning (Object Lock is not used; bucket versioning is enough for state rollback).
- [ ] On each bucket, deny public read in the bucket policy.

## 6. Provisioning order

After the steps above, the first real provisioning sequence is:

1. From `infra/live/dev`:
   ```bash
   tofu init
   tofu plan -out=tfplan
   tofu apply tfplan
   ```
2. Capture the kubeconfig output:
   ```bash
   tofu output -raw kubeconfig > ~/.kube/verolas-dev.yaml
   chmod 600 ~/.kube/verolas-dev.yaml
   export KUBECONFIG=~/.kube/verolas-dev.yaml
   kubectl get nodes
   ```
3. Install in cluster services with Helm (each from `infra/helm/<service>/values.yaml`):
   - cert-manager
   - Traefik ingress
   - Linkerd
   - HashiCorp Vault
   - Harbor
4. Initialize Vault, unseal, store the root token and unseal keys in the founder password vault.
5. Reproduce for `staging`, then `prod`.

## 7. Smoke test

After `dev` is up:

- [ ] `kubectl get nodes` returns 6 nodes, all `Ready`
- [ ] `kubectl get pods -A` shows core services running
- [ ] `dig verolas-dev.verolas.com` returns the Cloudflare proxied IP
- [ ] `curl https://verolas-dev.verolas.com/healthz` returns 200 (after Traefik is wired)

If any of the above fail, do not move to staging.
