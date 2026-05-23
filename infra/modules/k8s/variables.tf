variable "env" {
  description = "Environment name."
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be one of dev, staging, prod."
  }
}

variable "hcloud_token" {
  description = "Hetzner Cloud API token for this project."
  type        = string
  sensitive   = true
}

variable "network_region" {
  description = "Hetzner network region. eu-central for EU datacenters, us-east for Ashburn."
  type        = string
  default     = "eu-central"
}

variable "region" {
  description = "Hetzner Cloud datacenter for nodes. fsn1 (Falkenstein), nbg1 (Nuremberg), hel1 (Helsinki)."
  type        = string
  default     = "nbg1"
  validation {
    condition     = contains(["fsn1", "nbg1", "hel1"], var.region)
    error_message = "region must be one of fsn1 (Falkenstein), nbg1 (Nuremberg), hel1 (Helsinki)."
  }
}

variable "control_plane_count" {
  description = "Number of control plane nodes. Must be odd (1, 3, or 5)."
  type        = number
  default     = 3
  validation {
    condition     = var.control_plane_count == 1 || var.control_plane_count == 3 || var.control_plane_count == 5
    error_message = "control_plane_count must be 1, 3, or 5."
  }
}

variable "control_plane_server_type" {
  description = "Hetzner Cloud server type for control plane nodes. Minimum cx23."
  type        = string
  default     = "cx23"
}

variable "worker_count" {
  description = "Number of worker nodes. Set to 0 for single node clusters; set allow_scheduling_on_control_plane = true so workloads can run on the control plane."
  type        = number
  default     = 3
  validation {
    condition     = var.worker_count >= 0
    error_message = "worker_count must be 0 or greater."
  }
}

variable "worker_server_type" {
  description = "Hetzner Cloud server type for worker nodes. Minimum cx23."
  type        = string
  default     = "cx23"
}

variable "allow_scheduling_on_control_plane" {
  description = "If true, removes the NoSchedule taint from control plane nodes so workloads can run on them. Required when worker_count is 0."
  type        = bool
  default     = false
}

variable "ssh_public_key" {
  description = "SSH public key in OpenSSH format."
  type        = string
}

variable "ssh_private_key" {
  description = "Matching SSH private key contents."
  type        = string
  sensitive   = true
}

variable "k3s_channel" {
  description = "k3s release channel."
  type        = string
  default     = "v1.31"
}

variable "kube_apiserver_allow_ips" {
  description = "CIDRs allowed to reach the Kubernetes API server. Empty list means kube-hetzner uses its own default."
  type        = list(string)
  default     = []
}

variable "ssh_allow_ips" {
  description = "CIDRs allowed to SSH to nodes. Empty list means kube-hetzner uses its own default."
  type        = list(string)
  default     = []
}

variable "base_domain" {
  description = "Base domain attached to this cluster, e.g. dev.verolas.com. Used by kube-hetzner for resource labels."
  type        = string
}
