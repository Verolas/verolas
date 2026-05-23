variable "env" {
  description = "Environment name. Used as a prefix and label on all resources."
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be one of dev, staging, prod."
  }
}

variable "cidr" {
  description = "Top level CIDR for the Hetzner private network."
  type        = string
  default     = "10.42.0.0/16"
}

variable "nodes_subnet_cidr" {
  description = "Subnet CIDR for Kubernetes nodes."
  type        = string
  default     = "10.42.10.0/24"
}

variable "network_zone" {
  description = "Hetzner Cloud network zone."
  type        = string
  default     = "eu-central"
}

variable "delete_protection" {
  description = "If true, network cannot be deleted via the API. Set true for prod, false for dev."
  type        = bool
  default     = false
}

variable "kube_apiserver_allow_ips" {
  description = "Source CIDRs allowed to reach the Kubernetes API server. Tightly scoped to founder and CI runners."
  type        = list(string)
  default     = []
}

variable "ssh_allow_ips" {
  description = "Source CIDRs allowed to SSH to nodes. Tightly scoped to founder, bastion, and break-glass."
  type        = list(string)
  default     = []
}

variable "labels" {
  description = "Common labels applied to every resource."
  type        = map(string)
  default     = {}
}
