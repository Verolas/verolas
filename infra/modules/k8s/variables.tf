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

variable "network_id" {
  description = "Hetzner Cloud network ID created by the network module."
  type        = number
}

variable "network_cidr" {
  description = "Top level CIDR of the Hetzner network."
  type        = string
  default     = "10.42.0.0/16"
}

variable "region" {
  description = "Hetzner Cloud datacenter for nodes. Falkenstein for prod, Nuremberg for staging, either for dev."
  type        = string
  default     = "fsn1"
  validation {
    condition     = contains(["fsn1", "nbg1", "hel1"], var.region)
    error_message = "region must be one of fsn1 (Falkenstein), nbg1 (Nuremberg), hel1 (Helsinki)."
  }
}

variable "control_plane_count" {
  description = "Number of control plane nodes. Must be odd (1 or 3 for HA)."
  type        = number
  default     = 3
  validation {
    condition     = var.control_plane_count == 1 || var.control_plane_count == 3 || var.control_plane_count == 5
    error_message = "control_plane_count must be 1, 3, or 5."
  }
}

variable "control_plane_server_type" {
  description = "Hetzner Cloud server type for control plane nodes."
  type        = string
  default     = "ccx13"
}

variable "worker_count" {
  description = "Number of worker nodes."
  type        = number
  default     = 3
}

variable "worker_server_type" {
  description = "Hetzner Cloud server type for worker nodes."
  type        = string
  default     = "ccx23"
}

variable "ssh_public_key" {
  description = "SSH public key in OpenSSH format. Used by kube-hetzner to provision nodes."
  type        = string
}

variable "ssh_private_key" {
  description = "Path or contents of the matching SSH private key. Used by kube-hetzner during bootstrap. Set to null to skip and require manual SSH steps."
  type        = string
  sensitive   = true
  default     = null
}

variable "k3s_channel" {
  description = "k3s release channel. Pin to a specific minor (e.g. v1.31) for reproducibility."
  type        = string
  default     = "v1.31"
}

variable "kube_apiserver_allow_ips" {
  description = "CIDRs allowed to reach the Kubernetes API server."
  type        = list(string)
  default     = []
}

variable "ssh_allow_ips" {
  description = "CIDRs allowed to SSH to nodes."
  type        = list(string)
  default     = []
}

variable "base_domain" {
  description = "Base domain attached to this cluster, e.g. dev.verolas.com."
  type        = string
}
