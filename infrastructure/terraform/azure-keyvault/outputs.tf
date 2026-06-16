output "key_vault_id" {
  description = "Key Vault resource ID"
  value       = azurerm_key_vault.main.id
}

output "key_vault_uri" {
  description = "Key Vault URI"
  value       = azurerm_key_vault.main.vault_uri
}

output "secret_names" {
  description = "Names of secrets created"
  value       = [for s in azurerm_key_vault_secret.this : s.name]
}
