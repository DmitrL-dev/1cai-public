# AI Assistants Database Policy
path "database/*" {
  capabilities = ["read", "list"]
}

path "database/data/*" {
  capabilities = ["read", "create", "update", "delete", "list"]
}

path "database/metadata/*" {
  capabilities = ["read", "create", "update", "delete", "list"]
}

# Allow metadata
path "sys/mounts/database" {
  capabilities = ["read"]
}