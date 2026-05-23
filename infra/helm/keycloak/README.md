# Keycloak

OpenID Connect identity provider for Verolas. Issues access tokens that the API verifies, hosts the login UI, manages MFA, and stores user identity.

## Why Keycloak

- Mature, open source, self hosted, EU sovereign by default.
- Supports OIDC, SAML, social IdPs, federation against external user stores.
- TOTP MFA built in, plus WebAuthn for the future.
- Realm export and import is JSON, so realm configuration lives in code (`realm-template.json`).

Alternatives considered: Auth0 (US owned, not sovereign), Authentik (newer, less audit history), ZITADEL (newer, smaller ecosystem). Keycloak is the conservative pick for an audit grade product.

## Install on dev

```bash
export KUBECONFIG=~/.kube/verolas-dev.yaml

kubectl create namespace keycloak

# Admin credentials secret
kubectl -n keycloak create secret generic keycloak-admin \
  --from-literal=admin-password="$(openssl rand -base64 32)"

# Embedded Postgres credentials secret
kubectl -n keycloak create secret generic keycloak-db \
  --from-literal=admin-password="$(openssl rand -base64 32)" \
  --from-literal=user-password="$(openssl rand -base64 32)" \
  --from-literal=replication-password="$(openssl rand -base64 32)"

helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

helm install keycloak \
  --namespace keycloak \
  --version 23.0.0 \
  -f infra/helm/keycloak/values-dev.yaml \
  bitnami/keycloak
```

Watch the pod come up. First boot takes a couple of minutes while it initialises the embedded Postgres and runs the migration scripts.

## Install on prod (future)

Same flow with `values-prod.yaml`. Differences:

- Three replicas across separate nodes.
- External Postgres at `verolas-pg-rw.postgres.svc.cluster.local` (the CloudNativePG primary). A `keycloak` database and user are created beforehand via psql on the cluster.
- Public ingress at `auth.verolas.com` with cert manager and Traefik.
- Strict hostname enforcement.

## Apply the realm template

The realm template defines roles, clients, password and OTP policy, and event logging. Apply it once after the pod is ready, then update the SMTP and other placeholders via the Keycloak admin UI:

```bash
# Port forward the admin console
kubectl -n keycloak port-forward svc/keycloak 8080:80

# In another shell, get the admin password
kubectl -n keycloak get secret keycloak-admin \
  -o jsonpath='{.data.admin-password}' | base64 -d

# Then in the Keycloak admin UI at http://localhost:8080:
#   1. Sign in as admin
#   2. Add realm -> Import -> select infra/helm/keycloak/realm-template.json
#   3. Edit the realm to fill in SMTP, set the realm public key endpoints
#   4. Create the first user, assign the "owner" role on the verolas realm
#   5. Configure TOTP on first login

# Or scripted via kcadm.sh inside the pod (faster for repeated bootstraps):
# kubectl -n keycloak exec -it deploy/keycloak -- \
#   /opt/bitnami/keycloak/bin/kcadm.sh create realms -f /path/to/realm.json
```

The realm template enforces:

- Password policy: 12 chars minimum, mixed case, digits, special chars, no username/email reuse, 5 entries history, 90 day expiry.
- TOTP required on first login. SHA256, 6 digits, 30 second period, 1 step look ahead.
- Brute force protection: 5 failures lock the account for 15 minutes.
- Event logging: 90 days retention on user events and admin events.

## Six realm roles

The realm template ships these roles, mapping one to one with the database role enum from the tenancy migration:

| Role | Description |
| --- | --- |
| owner | Full org access; manages memberships, billing, settings |
| admin | Org management except billing and ownership transfer |
| reviewer | Reviews deliverables and signs off |
| engineer | Runs workflows, edits projects |
| viewer | Read only access to projects and deliverables |
| auditor | Read only access to audit logs and compliance data |

The application enforces these via the auth library at `services/auth/`.

## Verify

```bash
kubectl -n keycloak port-forward svc/keycloak 8080:80
curl -s http://localhost:8080/realms/verolas/.well-known/openid-configuration | jq .issuer
```

Expect `http://localhost:8080/realms/verolas`.
