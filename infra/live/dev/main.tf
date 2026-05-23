locals {
  env          = "dev"
  region       = "nbg1"
  zone_name    = "verolas.com"
  network_cidr = "10.42.0.0/16"
  labels = {
    env     = "dev"
    project = "verolas"
    owner   = "founder"
  }
}

module "network" {
  source = "../../modules/network"

  env                      = local.env
  cidr                     = local.network_cidr
  nodes_subnet_cidr        = "10.42.10.0/24"
  network_zone             = "eu-central"
  delete_protection        = false
  kube_apiserver_allow_ips = var.kube_apiserver_allow_ips
  ssh_allow_ips            = var.ssh_allow_ips
  labels                   = local.labels
}

module "k8s" {
  source = "../../modules/k8s"

  env          = local.env
  hcloud_token = var.hcloud_token
  network_id   = module.network.network_id
  network_cidr = local.network_cidr
  region       = local.region

  # Single node topology for early development. Scale up to 3 + 3 when product
  # workloads or a pilot make HA necessary; see infra/live/dev/README.md.
  control_plane_count               = 1
  control_plane_server_type         = "cx22"
  worker_count                      = 0
  worker_server_type                = "cx22"
  allow_scheduling_on_control_plane = true

  ssh_public_key  = file(pathexpand(var.ssh_public_key_path))
  ssh_private_key = file(pathexpand(var.ssh_private_key_path))

  k3s_channel              = "v1.31"
  kube_apiserver_allow_ips = var.kube_apiserver_allow_ips
  ssh_allow_ips            = var.ssh_allow_ips
  base_domain              = "${local.env}.${local.zone_name}"
}

module "dns" {
  source = "../../modules/cloudflare-dns"

  env       = local.env
  zone_name = local.zone_name

  # Single node dev has no Hetzner load balancer. Public DNS records are
  # deferred until either a load balancer or Cloudflare Tunnel is in place.
  env_subdomain_target          = ""
  env_subdomain_proxied         = false
  create_wildcard_env_subdomain = false
  create_caa                    = true
}
