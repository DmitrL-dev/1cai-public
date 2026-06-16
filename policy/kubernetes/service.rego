package kubernetes.service

is_managed {
  input.metadata.namespace == "1cai"
}

deny[msg] {
  input.kind == "Service"
  is_managed
  input.spec.type == "NodePort"
  msg := sprintf("service %s uses NodePort (not allowed)", [input.metadata.name])
}

deny[msg] {
  input.kind == "Service"
  is_managed
  not input.spec.selector
  msg := sprintf("service %s missing selector", [input.metadata.name])
}
