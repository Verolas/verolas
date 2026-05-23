# Network module

Sets up the Hetzner Cloud private network, node subnet, and per role firewalls for one Verolas environment.

## Inputs

See `variables.tf`. Required: `env`. The IP allowlists for SSH and the Kubernetes API server default to empty, which means lockdown until explicit IPs are provided.

## Outputs

- `network_id` and `network_name` to attach servers to.
- `control_plane_firewall_id` and `worker_firewall_id` to attach to the matching node pools.

## Notes

- We keep the network simple: one CIDR per environment, one subnet for nodes. Additional subnets for LBs or NAT are added when they are needed.
- Egress is unrestricted by default. Egress controls move into NetworkPolicies inside the cluster, not Hetzner firewalls.
- Delete protection should be on for `staging` and `prod`.
