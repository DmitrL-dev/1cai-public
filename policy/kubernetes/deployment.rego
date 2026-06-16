package kubernetes.deployment

is_managed {
  input.metadata.namespace == "1cai"
}

deny[msg] {
  input.kind == "Deployment"
  is_managed
  container := input.spec.template.spec.containers[_]
  not container.resources.limits
  msg := sprintf("deployment %s container %s is missing resource limits", [input.metadata.name, container.name])
}

deny[msg] {
  input.kind == "Deployment"
  is_managed
  container := input.spec.template.spec.containers[_]
  not container.resources.requests
  msg := sprintf("deployment %s container %s is missing resource requests", [input.metadata.name, container.name])
}

deny[msg] {
  input.kind == "Deployment"
  is_managed
  container := input.spec.template.spec.containers[_]
  endswith(container.image, ":latest")
  msg := sprintf("deployment %s container %s uses mutable tag :latest", [input.metadata.name, container.name])
}

deny[msg] {
  input.kind == "Deployment"
  is_managed
  container := input.spec.template.spec.containers[_]
  not has_probe(container.livenessProbe)
  msg := sprintf("deployment %s container %s missing livenessProbe", [input.metadata.name, container.name])
}

deny[msg] {
  input.kind == "Deployment"
  is_managed
  container := input.spec.template.spec.containers[_]
  not has_probe(container.readinessProbe)
  msg := sprintf("deployment %s container %s missing readinessProbe", [input.metadata.name, container.name])
}

default has_probe = false

has_probe(probe) {
  probe != null
}
