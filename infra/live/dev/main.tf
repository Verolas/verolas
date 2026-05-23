locals {
  env        = "dev"
  region     = "nbg1"
  zone_name  = "verolas.com"
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

  control_plane_count       = 3
  control_plane_server_type = "ccx13"
  worker_count              = 3
  worker_server_type        = "ccx23"

  ssh_public_key  = var.ssh_public_key
  ssh_private_key = var.ssh_private_key

  k3s_channel              = "v1.31"
  kube_apiserver_allow_ips = var.kube_apiserver_allow_ips
  ssh_allow_ips            = var.ssh_allow_ips
  base_domain              = "${local.env}.${local.zone_name}"
}

module "dns" {
  source = "../../modules/cloudflare-dns"

  env                           = local.env
  zone_name                     = local.zone_name
  env_subdomain_target          = module.k8s.load_balancer_ipv4
  env_subdomain_proxied         = false
  create_wildcard_env_subdomain = true
  create_caa                    = true
}
