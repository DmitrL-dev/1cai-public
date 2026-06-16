output "namespace" {
  description = "Namespace, в котором развёрнут 1cai-stack"
  value       = kubernetes_namespace.this.metadata[0].name
}

output "release_status" {
  description = "Статус Helm релиза"
  value       = helm_release.api.status
}
