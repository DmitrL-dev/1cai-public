# Основной Terraform файл для AWS
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.20"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.10"
    }
  }
  
  backend "s3" {
    bucket = "ai-assistants-terraform-state"
    key    = "infrastructure/terraform.tfstate"
    region = "us-west-2"
    encrypt = true
  }
}

# Провайдер AWS
provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "ai-assistants"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Провайдер Kubernetes (EKS)
provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  token                  = data.aws_eks_cluster_auth.this.token
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
}

# Провайдер Helm
provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    token                  = data.aws_eks_cluster_auth.this.token
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  }
}

# Переменные
variable "aws_region" {
  description = "AWS регион"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Окружение (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "cluster_name" {
  description = "Имя EKS кластера"
  type        = string
  default     = "ai-assistants-cluster"
}

variable "node_groups" {
  description = "Конфигурация групп узлов"
  type = map(object({
    instance_types = list(string)
    capacity_type  = string
    desired_size   = number
    max_size       = number
    min_size       = number
  }))
  default = {
    main = {
      instance_types = ["t3.large"]
      capacity_type  = "ON_DEMAND"
      desired_size   = 3
      max_size       = 10
      min_size       = 1
    }
  }
}

# Модули
module "vpc" {
  source = "./modules/vpc"
  
  name             = "${var.cluster_name}-vpc"
  cidr             = "10.0.0.0/16"
  azs              = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets   = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  enable_nat_gateway = true
  
  tags = {
    Name = "${var.cluster_name}-vpc"
  }
}

module "eks" {
  source = "./modules/eks"
  
  cluster_name    = var.cluster_name
  cluster_version = "1.28"
  
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets
  
  node_groups = var.node_groups
  
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent = true
    }
  }
}

module "rds" {
  source = "./modules/rds"
  
  identifier = "${var.cluster_name}-db"
  
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = "db.t3.medium"
  
  allocated_storage     = 100
  max_allocated_storage = 1000
  storage_encrypted     = true
  
  db_name  = "aiassistants"
  username = "postgres"
  
  password = random_password.db_password.result
  
  vpc_security_group_ids = [module.vpc.default_security_group_id]
  db_subnet_group_name   = module.vpc.database_subnet_group
  
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  
  enabled_cloudwatch_logs_exports = ["postgresql"]
  
  deletion_protection = var.environment == "prod" ? true : false
}

module "elasticache" {
  source = "./modules/elasticache"
  
  parameter_group_name = "default.redis7"
  node_type           = "cache.r6g.large"
  num_cache_nodes     = var.environment == "prod" ? 3 : 1
  engine_version      = "7.0"
  
  subnet_group_name = module.vpc.database_subnet_group
  
  security_group_ids = [module.vpc.default_security_group_id]
}

module "s3" {
  source = "./modules/s3"
  
  buckets = {
    ai-assistants-artifacts = {
      acl           = "private"
      force_destroy = var.environment != "prod"
      versioning    = true
      lifecycle_rule = [{
        id      = "transition"
        enabled = true
        transition = [
          {
            days          = 30
            storage_class = "STANDARD_IA"
          },
          {
            days          = 90
            storage_class = "GLACIER"
          }
        ]
      }]
    }
    ai-assistants-backups = {
      acl           = "private"
      force_destroy = false
      versioning    = true
      lifecycle_rule = [{
        id      = "archive"
        enabled = true
        expiration = {
          days = 365
        }
      }]
    }
  }
}

# Ресурсы данных
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_eks_cluster_auth" "this" {
  name = module.eks.cluster_name
}

# Рандомные пароли
resource "random_password" "db_password" {
  length  = 32
  special = true
}

# Выходные данные
output "cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = module.eks.cluster_endpoint
}

output "cluster_security_group_id" {
  description = "Security group ids attached to the cluster control plane"
  value       = module.eks.cluster_security_group_id
}

output "database_endpoint" {
  description = "RDS instance endpoint"
  value       = module.rds.db_instance_endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "ElastiCache cluster endpoint"
  value       = module.elasticache.cluster_endpoint
  sensitive   = true
}

output "s3_bucket_artifacts" {
  description = "S3 bucket for artifacts"
  value       = module.s3.s3_bucket_ids["ai-assistants-artifacts"]
}

output "cluster_iam_role_name" {
  description = "IAM role name associated with EKS cluster"
  value       = module.eks.cluster_iam_role_name
}