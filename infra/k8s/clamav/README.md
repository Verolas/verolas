# ClamAV

ClamAV daemon used by the upload pipeline to scan every file before it lands in `ready` status. The API uses the `verolas_storage.clamd.ClamdClient` library to stream files over TCP to this daemon.

## Why ClamAV

- Open source, EU sovereign, runs in our cluster.
- Speaks the standard `clamd` protocol that everyone uses for stream scanning.
- Signature updates run automatically via `freshclam` inside the pod.
- Detects 95%+ of common malware; the gap above 95% is closed by:
  - Sandbox analysis of macro bearing Office files (XLSM, DOCM, PPTM). Macro detection happens in the API via `verolas_storage.file_kinds.classify_file()`; the actual sandbox runs in the firm knowledge ingestion workstream.
  - Optional second engine in prod, evaluated when customer needs warrant the cost.

## Install on dev

```bash
export KUBECONFIG=~/.kube/verolas-dev.yaml

kubectl apply -f infra/k8s/clamav/namespace.yaml
kubectl apply -f infra/k8s/clamav/deployment.yaml
```

First start takes about five minutes because freshclam downloads the full signature set (~250 MB). Readiness gate is open as soon as clamd accepts TCP. Liveness probe waits five minutes so freshclam's initial sync finishes without restart loops.

Verify:

```bash
kubectl -n clamav port-forward svc/clamav 3310:3310 &
echo "PING" | nc -w 5 -C localhost 3310
# expect: PONG
kill %1
```

Or run the EICAR test file through the API once it is wired:

```bash
curl -X POST http://localhost:8000/v1/files \
  -H "Authorization: Bearer <token>" \
  -d '{"filename": "eicar.txt", "size_bytes": 68}'
# upload the EICAR string via the returned presigned URL
# call complete and expect status quarantined
```

## Resource notes

clamd holds the signature database in memory, so the pod requests 1 GiB and limits at 2 GiB. On the single CX23 dev node this is significant: combined with Postgres and Redis from earlier PRs, the cluster is getting tight. Scaling up the node is the near term call when ClamAV joins.

## Air gapped clusters

For air gapped or sovereignty restricted environments, freshclam can pull from a mirror inside the customer's perimeter. The Deployment exposes the freshclam config via an environment variable; flip to `CLAMAV_NO_FRESHCLAMD=true` and mount signatures from a side car or scheduled CronJob.
