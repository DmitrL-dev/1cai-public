resource "kubernetes_namespace" "this" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "app.kubernetes.io/part-of"    = "1cai-stack"
    }
  }
}

resource "helm_release" "api" {
  name       = var.release_name
  namespace  = kubernetes_namespace.this.metadata[0].name
  repository = "https://charts.1cai.dev/local"
  chart      = "1cai-stack"
  version    = var.chart_version

  dynamic "set" {
    for_each = {
      "image.repository" = "ghcr.io/1c-ai-stack/api"
      "image.tag"        = "latest"
    }
    content {
      name  = set.key
      value = set.value
    }
  }

  values = concat([
    file("../helm/1cai-stack/values.yaml")
  ], var.values_files)

  depends_on = [kubernetes_namespace.this]
}
