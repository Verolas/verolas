variable "env" {
  description = "Environment name."
  type        = string
}

variable "zone_name" {
  description = "Apex zone, e.g. verolas.com. The zone must already exist in Cloudflare."
  type        = string
}

variable "apex_target" {
  description = "IPv4 the apex A record points to. Typically the marketing site IP, not a cluster ingress."
  type        = string
  default     = ""
}

variable "create_apex" {
  description = "Whether to create the apex A record. Set false until the marketing site is live."
  type        = bool
  default     = false
}

variable "create_www" {
  description = "Whether to create the www CNAME pointing at the apex."
  type        = bool
  default     = false
}

variable "env_subdomain_target" {
  description = "IPv4 the <env> subdomain points to (typically the cluster load balancer)."
  type        = string
  default     = ""
}

variable "env_subdomain_proxied" {
  description = "Whether the env subdomain is Cloudflare proxied (orange cloud)."
  type        = bool
  default     = true
}

variable "create_wildcard_env_subdomain" {
  description = "Whether to create the wildcard CNAME for the env subdomain."
  type        = bool
  default     = true
}

variable "create_caa" {
  description = "Whether to create a CAA record restricting issuance to Let's Encrypt."
  type        = bool
  default     = true
}
