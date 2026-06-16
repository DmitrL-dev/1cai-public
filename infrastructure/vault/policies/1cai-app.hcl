path "secret/data/1cai/*" {
  capabilities = ["read"]
}

path "secret/metadata/1cai/*" {
  capabilities = ["list"]
}

path "sys/leases/renew" {
  capabilities = ["update"]
}

path "sys/leases/revoke" {
  capabilities = ["update"]
}
