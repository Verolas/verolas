output "network_id" {
  description = "Hetzner Cloud network ID."
  value       = hcloud_network.this.id
}

output "network_name" {
  description = "Hetzner Cloud network name."
  value       = hcloud_network.this.name
}

output "subnet_ip_range" {
  description = "Node subnet CIDR."
  value       = hcloud_network_subnet.nodes.ip_range
}

output "control_plane_firewall_id" {
  description = "Firewall ID to attach to control plane nodes."
  value       = hcloud_firewall.control_plane.id
}

output "worker_firewall_id" {
  description = "Firewall ID to attach to worker nodes."
  value       = hcloud_firewall.worker.id
}
