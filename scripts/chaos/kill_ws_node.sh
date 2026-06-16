#!/usr/bin/env bash
set -euo pipefail

# Chaos experiment: terminate a BA websocket worker process/container.
# Usage:
#   ./scripts/chaos/kill_ws_node.sh process <pattern>
#   ./scripts/chaos/kill_ws_node.sh docker <container_name>
#
# Example:
#   ./scripts/chaos/kill_ws_node.sh process "uvicorn.*main:app.*8000"
#   ./scripts/chaos/kill_ws_node.sh docker ba-websocket-1

MODE="${1:-}"
TARGET="${2:-}"

if [[ -z "${MODE}" || -z "${TARGET}" ]]; then
  echo "Usage: $0 <process|docker> <pattern|container>" >&2
  exit 2
fi

case "${MODE}" in
  process)
    PIDS=$(pgrep -f "${TARGET}" || true)
    if [[ -z "${PIDS}" ]]; then
      echo "[WARN] No process matching '${TARGET}' found."
      exit 0
    fi
    echo "[INFO] Killing processes: ${PIDS}"
    kill -9 ${PIDS}
    ;;
  docker)
    if ! command -v docker >/dev/null 2>&1; then
      echo "[ERROR] Docker CLI not found." >&2
      exit 3
    fi
    echo "[INFO] Stopping container ${TARGET}"
    docker kill "${TARGET}"
    ;;
  *)
    echo "[ERROR] Mode must be 'process' or 'docker'." >&2
    exit 4
    ;;
esac

echo "[INFO] Chaos action completed."

