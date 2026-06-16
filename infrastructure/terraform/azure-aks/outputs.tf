output "kube_admin_config" {
  description = "Admin kubeconfig"
  value       = azurerm_kubernetes_cluster.main.kube_admin_config_raw
  sensitive   = true
}

output "resource_group" {
  value       = azurerm_resource_group.main.name
  description = "Resource group name"
}
