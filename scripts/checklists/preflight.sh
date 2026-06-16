#!/usr/bin/env bash
set -euo pipefail

LOG_FILE=$(mktemp)
trap 'rm -f "$LOG_FILE"' EXIT

exec > >(tee -a "$LOG_FILE") 2>&1

log() {
  printf '[preflight] %s\n' "$*"
}

commands=(
  "make check-runtime"
  "make lint"
  "make test"
  "make policy-check"
  "bash scripts/security/run_checkov.sh"
)

status=0
for cmd in "${commands[@]}"; do
  log "running: $cmd"
  if eval "$cmd"; then
    log "ok: $cmd"
    echo
  else
    log "FAILED: $cmd"
    status=1
    break
  fi
done

if [[ $status -eq 0 ]]; then
  log "preflight checklist completed"
else
  log "preflight checklist failed"
fi

if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
  python - "$SLACK_WEBHOOK_URL" "$status" "$LOG_FILE" <<'PY'
import json
import pathlib
import sys
import textwrap
import urllib.request

url, status, path = sys.argv[1:4]
status_text = "SUCCESS" if status == "0" else "FAIL"
log = pathlib.Path(path).read_text()
log_tail = "\n".join(log.rstrip().splitlines()[-30:])
text = f"*Preflight {status_text}*\n```{log_tail}```"
req = urllib.request.Request(url, data=json.dumps({"text": text}).encode(), headers={'Content-Type': 'application/json'})
urllib.request.urlopen(req)
PY
fi

exit $status
