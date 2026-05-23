terraform {
  required_version = ">= 1.8.0"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
  }
}

resource "hcloud_network" "this" {
  name              = "${var.env}-network"
  ip_range          = var.cidr
  delete_protection = var.delete_protection

  labels = merge(var.labels, {
    env       = var.env
    component = "network"
  })
}

resource "hcloud_network_subnet" "nodes" {
  network_id   = hcloud_network.this.id
  type         = "cloud"
  network_zone = var.network_zone
  ip_range     = var.nodes_subnet_cidr
}

resource "hcloud_firewall" "control_plane" {
  name = "${var.env}-control-plane"

  rule {
    description = "kube-apiserver from founder IP allowlist"
    direction   = "in"
    protocol    = "tcp"
    port        = "6443"
    source_ips  = var.kube_apiserver_allow_ips
  }

  rule {
    description = "etcd peer traffic inside cluster network"
    direction   = "in"
    protocol    = "tcp"
    port        = "2379-2380"
    source_ips  = [var.cidr]
  }

  rule {
    description = "kubelet inside cluster network"
    direction   = "in"
    protocol    = "tcp"
    port        = "10250"
    source_ips  = [var.cidr]
  }

  rule {
    description = "SSH from bastion or founder IP allowlist only"
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = var.ssh_allow_ips
  }

  rule {
    description = "ICMP from cluster network"
    direction   = "in"
    protocol    = "icmp"
    source_ips  = [var.cidr]
  }

  labels = merge(var.labels, {
    env       = var.env
    component = "firewall"
    role      = "control-plane"
  })
}

resource "hcloud_firewall" "worker" {
  name = "${var.env}-worker"

  rule {
    description = "NodePort range, opened only when LoadBalancer is not in use"
    direction   = "in"
    protocol    = "tcp"
    port        = "30000-32767"
    source_ips  = [var.cidr]
  }

  rule {
    description = "kubelet inside cluster network"
    direction   = "in"
    protocol    = "tcp"
    port        = "10250"
    source_ips  = [var.cidr]
  }

  rule {
    description = "SSH from bastion or founder IP allowlist only"
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = var.ssh_allow_ips
  }

  rule {
    description = "Pod network overlay (flannel VXLAN or Cilium VXLAN)"
    direction   = "in"
    protocol    = "udp"
    port        = "8472"
    source_ips  = [var.cidr]
  }

  labels = merge(var.labels, {
    env       = var.env
    component = "firewall"
    role      = "worker"
  })
}
