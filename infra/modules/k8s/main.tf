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

  providers = {
    hcloud = hcloud
  }

  hcloud_token = var.hcloud_token
  cluster_name = "${var.env}-cluster"

  network_region = var.network_region

  ssh_public_key  = var.ssh_public_key
  ssh_private_key = var.ssh_private_key

  control_plane_nodepools = [
    {
      name        = "control-plane-${var.region}"
      server_type = var.control_plane_server_type
      location    = var.region
      count       = var.control_plane_count
      labels      = []
      taints      = []
    }
  ]

  agent_nodepools = [
    {
      name        = "worker-${var.region}"
      server_type = var.worker_server_type
      location    = var.region
      count       = var.worker_count
      labels      = []
      taints      = []
    }
  ]

  load_balancer_type     = "lb11"
  load_balancer_location = var.region

  allow_scheduling_on_control_plane = var.allow_scheduling_on_control_plane

  initial_k3s_channel       = var.k3s_channel
  automatically_upgrade_k3s = false
  automatically_upgrade_os  = false

  disable_kube_proxy    = false
  cni_plugin            = "cilium"
  enable_cert_manager   = false
  enable_metrics_server = true

  enable_klipper_metal_lb = false
  ingress_controller      = "none"

  base_domain = var.base_domain

  create_kubeconfig    = true
  create_kustomization = false

  firewall_kube_api_source = length(var.kube_apiserver_allow_ips) > 0 ? var.kube_apiserver_allow_ips : null
  firewall_ssh_source      = length(var.ssh_allow_ips) > 0 ? var.ssh_allow_ips : null

  extra_kustomize_parameters = {
    env = var.env
  }
}
