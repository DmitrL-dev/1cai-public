package kubernetes.security

is_managed {
  input.metadata.namespace == "1cai"
}

deny[msg] {
  input.kind == "Deployment"
  is_managed
  container := input.spec.template.spec.containers[_]
  not container.securityContext.runAsNonRoot
  msg := sprintf("deployment %s container %s must set securityContext.runAsNonRoot", [input.metadata.name, container.name])
}
