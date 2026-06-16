output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_certificate_authority_data" {
  description = "Cluster CA"
  value       = module.eks.cluster_certificate_authority_data
}

output "aws_auth_configmap" {
  description = "AWS auth configmap"
  value       = module.eks.aws_auth_configmap_yaml
}
