#!/usr/bin/env bash
set -euo pipefail

# Chaos experiment: block outbound traffic to Jira for a short period.
# Usage: ./scripts/chaos/block_jira.sh <jira_host> <duration_seconds>
#
# Example:
#   sudo ./scripts/chaos/block_jira.sh atlassian.net 300
#
# Requirements:
#   - Linux host with iptables (or nftables via iptables-nft)
#   - sudo/root privileges

if [[ "${EUID}" -ne 0 ]]; then
  echo "[ERROR] Run as root or via sudo." >&2
  exit 1
fi

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <jira_host> <duration_seconds>" >&2
  exit 2
fi

JIRA_HOST="$1"
DURATION="$2"

echo "[INFO] Resolving ${JIRA_HOST} ..."
JIRA_IP=$(getent ahosts "${JIRA_HOST}" | awk 'NR==1 {print $1}')

if [[ -z "${JIRA_IP}" ]]; then
  echo "[ERROR] Unable to resolve ${JIRA_HOST}" >&2
  exit 3
fi

trap 'iptables -D OUTPUT -d "${JIRA_IP}" -j DROP 2>/dev/null || true' EXIT

echo "[INFO] Blocking traffic to ${JIRA_HOST} (${JIRA_IP}) for ${DURATION}s"
iptables -I OUTPUT -d "${JIRA_IP}" -j DROP

sleep "${DURATION}" || true

echo "[INFO] Restoring connectivity"
iptables -D OUTPUT -d "${JIRA_IP}" -j DROP

