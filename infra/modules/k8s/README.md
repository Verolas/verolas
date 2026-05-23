# Kubernetes module

Thin wrapper over the `kube-hetzner/kube-hetzner` Terraform module. Brings up a Hetzner Cloud Kubernetes cluster with the Verolas defaults:

- k3s distribution, pinned channel
- 3 control plane + 3 worker nodes
- Cilium CNI
- Hetzner Cloud Load Balancer in front, no Klipper
- No bundled ingress controller (we install Traefik separately via Helm)
- No bundled cert-manager (we install it separately, version pinned)

## Why kube-hetzner

It is the de facto production module for Kubernetes on Hetzner Cloud. Maintained, widely used, and supports the exact topology the bible specifies (control plane + worker pools on CCX). The upstream module surface is large; this wrapper exposes only the inputs Verolas needs.

## Migration path to upstream Kubernetes

k3s is acceptable for dev and staging. For production GA the migration target is upstream Kubernetes 1.31+ provisioned via kubeadm or Cluster API on Hetzner. That migration is captured as a future ADR; doing it now would be premature.

## Outputs

- `kubeconfig` is sensitive. Write it to a file with `chmod 600`.
- `control_plane_ipv4` and `load_balancer_ipv4` feed into the Cloudflare DNS module.
