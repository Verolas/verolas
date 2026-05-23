output "kubeconfig" {
  description = "Kubeconfig file contents for kubectl access. Mark sensitive, never log."
  value       = module.cluster.kubeconfig
  sensitive   = true
}

output "control_plane_ipv4" {
  description = "Public IPv4 addresses of control plane nodes."
  value       = module.cluster.control_planes_public_ipv4
}

output "load_balancer_ipv4" {
  description = "Public IPv4 of the cluster load balancer."
  value       = module.cluster.lb_ingress_ipv4
}

output "cluster_name" {
  description = "Cluster name."
  value       = module.cluster.cluster_name
}
