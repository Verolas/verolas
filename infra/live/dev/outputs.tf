output "kubeconfig" {
  description = "Kubeconfig for the dev cluster. Write to a file and never log."
  value       = module.k8s.kubeconfig
  sensitive   = true
}

output "control_plane_ipv4" {
  description = "Control plane public IPv4 addresses."
  value       = module.k8s.control_plane_ipv4
}

output "load_balancer_ipv4" {
  description = "Cluster load balancer public IPv4."
  value       = module.k8s.load_balancer_ipv4
}

output "env_fqdn" {
  description = "Fully qualified domain for the dev cluster ingress."
  value       = module.dns.env_fqdn
}
