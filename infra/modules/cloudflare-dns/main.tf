terraform {
  required_version = ">= 1.8.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.40"
    }
  }
}

data "cloudflare_zone" "this" {
  name = var.zone_name
}

resource "cloudflare_record" "apex" {
  count = var.create_apex ? 1 : 0

  zone_id = data.cloudflare_zone.this.id
  name    = "@"
  content = var.apex_target
  type    = "A"
  proxied = true
  ttl     = 1
  comment = "Apex record for ${var.zone_name}, managed by infra/modules/cloudflare-dns"
}

resource "cloudflare_record" "www" {
  count = var.create_www ? 1 : 0

  zone_id = data.cloudflare_zone.this.id
  name    = "www"
  content = var.zone_name
  type    = "CNAME"
  proxied = true
  ttl     = 1
  comment = "www to apex, managed by infra/modules/cloudflare-dns"
}

resource "cloudflare_record" "env_subdomain" {
  count = var.env_subdomain_target == "" ? 0 : 1

  zone_id = data.cloudflare_zone.this.id
  name    = var.env
  content = var.env_subdomain_target
  type    = "A"
  proxied = var.env_subdomain_proxied
  ttl     = 1
  comment = "${var.env} cluster ingress, managed by infra/modules/cloudflare-dns"
}

resource "cloudflare_record" "wildcard_env" {
  count = var.create_wildcard_env_subdomain && var.env_subdomain_target != "" ? 1 : 0

  zone_id = data.cloudflare_zone.this.id
  name    = "*.${var.env}"
  content = "${var.env}.${var.zone_name}"
  type    = "CNAME"
  proxied = var.env_subdomain_proxied
  ttl     = 1
  comment = "Wildcard for ${var.env} cluster services, managed by infra/modules/cloudflare-dns"
}

resource "cloudflare_record" "caa_letsencrypt" {
  count = var.create_caa ? 1 : 0

  zone_id = data.cloudflare_zone.this.id
  name    = "@"
  type    = "CAA"
  ttl     = 3600
  data {
    flags = "0"
    tag   = "issue"
    value = "letsencrypt.org"
  }
}
