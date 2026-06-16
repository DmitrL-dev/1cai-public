# AI Assistants Application Policy
path "ai-assistants/data/*" {
  capabilities = ["read", "create", "update"]
}

path "ai-assistants/metadata/*" {
  capabilities = ["read", "update"]
}

path "ai-assistants/config/*" {
  capabilities = ["read"]
}

path "ai-assistants/creds/*" {
  capabilities = ["read", "create", "update", "delete"]
}

# Dynamic database credentials
path "ai-assistants/creds/postgres/*" {
  capabilities = ["read", "create"]
}

# Static secrets
path "ai-assistants/static/*" {
  capabilities = ["read"]
}

# Monitoring and health
path "sys/health" {
  capabilities = ["read"]
}

path "sys/mounts" {
  capabilities = ["read"]
}