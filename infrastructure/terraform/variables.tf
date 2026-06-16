variable "kubeconfig_path" {
  type        = string
  description = "Путь к kubeconfig (по умолчанию ~/.kube/config)"
  default     = "~/.kube/config"
}

variable "kubeconfig_context" {
  type        = string
  description = "Контекст kubeconfig (по умолчанию kind-1cai-devops)"
  default     = "kind-1cai-devops"
}

variable "namespace" {
  type        = string
  description = "Namespace для размещения 1cai"
  default     = "1cai"
}

variable "release_name" {
  type        = string
  description = "Имя релиза Helm"
  default     = "1cai"
}

variable "chart_version" {
  type        = string
  description = "Версия Helm chart"
  default     = "0.1.0"
}

variable "values_files" {
  type        = list(string)
  description = "Дополнительные файлы values.yaml"
  default     = []
}
