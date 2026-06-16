variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "eu-central-1"
}

variable "cluster_name" {
  type        = string
  description = "EKS cluster name"
  default     = "1cai-dev"
}

variable "cluster_version" {
  type        = string
  description = "Kubernetes version"
  default     = "1.29"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR"
  default     = "10.0.0.0/16"
}

variable "private_subnets" {
  type        = list(string)
  description = "Private subnet CIDRs"
  default     = [
    "10.0.1.0/24",
    "10.0.2.0/24",
    "10.0.3.0/24"
  ]
}

variable "public_subnets" {
  type        = list(string)
  description = "Public subnet CIDRs"
  default     = [
    "10.0.101.0/24",
    "10.0.102.0/24",
    "10.0.103.0/24"
  ]
}

variable "node_instance_types" {
  type        = list(string)
  description = "Instance types for EKS managed node group"
  default     = ["t3.large"]
}

variable "node_desired_size" {
  type        = number
  description = "Desired node count"
  default     = 2
}

variable "node_min_size" {
  type        = number
  description = "Minimum node count"
  default     = 1
}

variable "node_max_size" {
  type        = number
  description = "Maximum node count"
  default     = 4
}

variable "node_capacity_type" {
  type        = string
  description = "Capacity type (ON_DEMAND or SPOT)"
  default     = "ON_DEMAND"
}
