package terraform.azure

deny[msg] {
  input.resource_type == "azurerm_virtual_network"
  not input.change.after.tags.Owner
  msg = sprintf("Azure VNet %s missing Owner tag", [input.address])
}

deny[msg] {
  input.resource_type == "azurerm_key_vault"
  input.change.after.purge_protection_enabled == false
  msg = sprintf("KeyVault %s must enable purge protection", [input.address])
}
