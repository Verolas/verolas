variable "hcloud_token" {
  description = "Hetzner Cloud API token for the verolas-dev project."
  type        = string
  sensitive   = true
}

variable "hetzner_s3_access_key" {
  description = "Hetzner Object Storage access key. Used by the S3 state backend."
  type        = string
  sensitive   = true
}

variable "hetzner_s3_secret_key" {
  description = "Hetzner Object Storage secret key. Used by the S3 state backend."
  type        = string
  sensitive   = true
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token scoped to the verolas.com zone."
  type        = string
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID."
  type        = string
}

variable "ssh_public_key" {
  description = "SSH public key in OpenSSH format. Added to all dev nodes for break glass access."
  type        = string
}

variable "ssh_private_key" {
  description = "SSH private key. Used by kube-hetzner during bootstrap only."
  type        = string
  sensitive   = true
}

variable "kube_apiserver_allow_ips" {
  description = "CIDRs allowed to reach the kube apiserver in dev. Tighten to founder home or VPN."
  type        = list(string)
  default     = []
}

variable "ssh_allow_ips" {
  description = "CIDRs allowed to SSH to dev nodes. Tighten to founder home or VPN."
  type        = list(string)
  default     = []
}
