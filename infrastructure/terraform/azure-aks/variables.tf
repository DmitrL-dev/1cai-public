variable "azure_subscription_id" {
  type        = string
  description = "Azure subscription ID"
}

variable "cluster_name" {
  type        = string
  description = "AKS cluster name"
  default     = "1cai-aks"
}

variable "location" {
  type        = string
  description = "Azure region"
  default     = "westeurope"
}

variable "vnet_cidr" {
  type        = string
  description = "VNet CIDR"
  default     = "10.10.0.0/16"
}

variable "subnet_cidr" {
  type        = string
  description = "Subnet CIDR"
  default     = "10.10.1.0/24"
}

variable "node_count" {
  type        = number
  description = "AKS node count"
  default     = 2
}

variable "node_vm_size" {
  type        = string
  description = "VM size"
  default     = "Standard_DS3_v2"
}
