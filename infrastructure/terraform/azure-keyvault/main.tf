terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

resource "azurerm_resource_group" "kv" {
  count    = var.create_resource_group ? 1 : 0
  name     = var.resource_group_name
  location = var.location
}

locals {
  rg_name = var.create_resource_group ? azurerm_resource_group.kv[0].name : var.resource_group_name
}

resource "azurerm_key_vault" "main" {
  name                        = var.key_vault_name
  location                    = var.location
  resource_group_name         = local.rg_name
  tenant_id                   = var.tenant_id
  sku_name                    = var.sku_name
  purge_protection_enabled    = var.purge_protection_enabled
  soft_delete_retention_days  = var.soft_delete_retention_days
  enable_rbac_authorization   = false

  network_acls {
    bypass = "AzureServices"
    default_action = "Allow"
  }

  tags = var.tags
}

resource "azurerm_key_vault_secret" "this" {
  for_each            = var.secrets
  name                = each.key
  value               = each.value
  key_vault_id        = azurerm_key_vault.main.id
  content_type        = "text/plain"
  depends_on          = [azurerm_key_vault.main]
}

resource "azurerm_key_vault_access_policy" "this" {
  for_each            = { for p in var.access_policies : p.object_id => p }
  key_vault_id        = azurerm_key_vault.main.id
  tenant_id           = var.tenant_id
  object_id           = each.value.object_id
  secret_permissions  = lookup(each.value, "secret_permissions", ["Get", "List"])
  certificate_permissions = lookup(each.value, "certificate_permissions", [])
  key_permissions     = lookup(each.value, "key_permissions", [])
}
