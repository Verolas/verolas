output "zone_id" {
  description = "Cloudflare zone ID."
  value       = data.cloudflare_zone.this.id
}

output "env_fqdn" {
  description = "Fully qualified domain for the environment cluster."
  value       = "${var.env}.${var.zone_name}"
}
