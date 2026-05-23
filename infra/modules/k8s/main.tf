terraform {
  required_version = ">= 1.8.0"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
  }
}

module "cluster" {
  source  = "kube-hetzner/kube-hetzner/hcloud"
  version = "~> 2.18"

  hcloud_token = var.hcloud_token
  cluster_name = "${var.env}-cluster"

  network_id      = var.network_id
  network_ipv4_cidr = var.network_cidr
  cluster_ipv4_cidr = "10.244.0.0/16"
  service_ipv4_cidr = "10.245.0.0/16"

  ssh_public_key  = var.ssh_public_key
  ssh_private_key = var.ssh_private_key

  control_plane_nodepools = [
    {
      name        = "control-plane-${var.region}"
      server_type = var.control_plane_server_type
      location    = var.region
      count       = var.control_plane_count
      labels      = ["nodepool=control-plane"]
      taints      = []
    }
  ]

  agent_nodepools = var.worker_count > 0 ? [
    {
      name        = "worker-${var.region}"
      server_type = var.worker_server_type
      location    = var.region
      count       = var.worker_count
      labels      = ["nodepool=worker"]
      taints      = []
    }
  ] : []

  load_balancer_type      = "lb11"
  load_balancer_location  = var.region

  allow_scheduling_on_control_plane = var.allow_scheduling_on_control_plane

  initial_k3s_channel     = var.k3s_channel
  automatically_upgrade_k3s     = false
  automatically_upgrade_os      = false

  disable_kube_proxy   = false
  cni_plugin           = "cilium"
  enable_cert_manager  = false
  enable_metrics_server = true

  use_klipper_lb       = false
  ingress_controller   = "none"

  extra_firewall_rules = []

  base_domain         = var.base_domain
  cluster_dns_provider = "cloudflare"

  create_kubeconfig    = true
  create_kustomization = false

  firewall_kube_api_source = var.kube_apiserver_allow_ips
  firewall_ssh_source      = var.ssh_allow_ips

  extra_kustomize_parameters = {
    env = var.env
  }
}
