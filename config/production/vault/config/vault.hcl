# Vault Server Configuration
ui = true

# API and Cluster Addresses
api_addr = "http://0.0.0.0:8200"
cluster_addr = "http://0.0.0.0:8201"

# Data Storage
storage "file" {
  path = "/vault/data"
}

# Telemetry
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname = true
}

# HTTP Configuration
http_response_headers {
  "Strict-Transport-Security" = "max-age=31536000"
  "Content-Security-Policy" = "default-src 'self'"
}

# Max Request Size
max_request_size = 10485760

# Request Timeout
request_timeout = "300s"

# Default Lease TTL
default_lease_ttl = "168h"

# Max Lease TTL
max_lease_ttl = "720h"

# Disable Mlock
disable_mlock = true

# Log Level
log_level = "INFO"

# Audit Configuration
audit {
  file_path = "/var/log/vault/audit.log"
  log_raw = false
}

# Listener Configuration
listener "tcp" {
  address = "0.0.0.0:8200"
  tls_disable = true
  
  # Rate limiting
  http_read_timeout = "300s"
  http_write_timeout = "300s"
  http_idle_timeout = "300s"
}

# Seals (производственная конфигурация с AWS KMS или HSM)
# seal "awskms" {
#   region     = "us-west-2"
#   kms_key_id = "alias/vault-kms-key"
# }

# Seal "pkcs11" {
#   library   = "/usr/lib/pkcs11/libsofthsm2.so"
#   slot      = "0"
#   pin       = "vault_pin"
#   key_label = "vault-key"
# }

# Experimental Features
experiments = ["response-wrapping"]

# Disable Queries
disable_performance_standby = true