# Keycloak theme overlay

This directory holds the Verolas-branded Keycloak login theme and the kustomize
overlay that ships it to the dev cluster.

## Layout

```
themes/verolas/login/
  theme.properties           parent=keycloak.v2, points at our CSS
  template.ftl               page chrome with our logo + footer
  login.ftl                  sign-in form copy + social provider buttons
  register.ftl               sign-up form copy
  resources/css/styles.css   brand tokens that override PatternFly variables
  resources/img/logo.svg     inline wordmark
```

## Apply

```bash
kubectl apply -k infra/k8s/keycloak
kubectl patch deploy keycloak -n keycloak \
  --type strategic --patch-file infra/k8s/keycloak/deployment-patch.yaml
kubectl rollout status deploy/keycloak -n keycloak
```

The realm needs to be told to use the theme. Inside a Keycloak pod:

```bash
/opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 --realm master \
  --user admin --password "$KC_ADMIN_PASSWORD"

/opt/keycloak/bin/kcadm.sh update realms/verolas \
  -s 'loginTheme=verolas' \
  -s 'registrationAllowed=true' \
  -s 'resetPasswordAllowed=true' \
  -s 'rememberMe=true' \
  -s 'verifyEmail=false' \
  -s 'registrationEmailAsUsername=true'
```

Verify by hitting `https://auth.dev.verolas.com/realms/verolas/account` in a
browser and checking the wordmark, footer, and our brand colours render.

## Iterating on the theme

Edit a file under `themes/verolas/login/`, then:

```bash
kubectl apply -k infra/k8s/keycloak
kubectl rollout restart deploy/keycloak -n keycloak
```

Theme caching is disabled in the deployment patch (`KC_SPI_THEME_CACHE_*=false`)
so a pod restart is enough; no need to bust browser caches manually beyond a
hard refresh.

## Adding a social identity provider

The theme will automatically render any IdP Keycloak knows about. To add
Google or Microsoft:

```bash
/opt/keycloak/bin/kcadm.sh create identity-provider/instances -r verolas -f - <<'JSON'
{
  "alias": "google",
  "providerId": "google",
  "displayName": "Google",
  "enabled": true,
  "config": {
    "clientId": "<from Google Cloud>",
    "clientSecret": "<from Google Cloud>",
    "syncMode": "IMPORT"
  }
}
JSON
```

The redirect URI Google needs:
`https://auth.dev.verolas.com/realms/verolas/broker/google/endpoint`.
