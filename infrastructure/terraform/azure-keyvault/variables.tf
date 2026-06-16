variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "tenant_id" {
  description = "Azure tenant ID"
  type        = string
}

variable "resource_group_name" {
  description = "Resource group name"
  type        = string
}

variable "create_resource_group" {
  description = "Create resource group if true"
  type        = bool
  default     = false
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "key_vault_name" {
  description = "Key Vault name"
  type        = string
}

variable "sku_name" {
  description = "Key Vault SKU"
  type        = string
  default     = "standard"
}

variable "purge_protection_enabled" {
  description = "Enable purge protection"
  type        = bool
  default     = true
}

variable "soft_delete_retention_days" {
  description = "Soft delete retention period"
  type        = number
  default     = 90
}

variable "secrets" {
  description = "Map of secret name => value"
  type        = map(string)
  default     = {}
}

variable "access_policies" {
  description = "List of access policies (object_id, secret_permissions, key_permissions, certificate_permissions)"
  type        = list(object({
    object_id              = string
    secret_permissions     = optional(list(string))
    key_permissions        = optional(list(string))
    certificate_permissions= optional(list(string))
  }))
  default = []
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
