
#!/usr/bin/env python3
"""Send simple message with cost data to Microsoft Teams webhook."""

from __future__ import annotations

import json
import os
import sys
from typing import Iterable

import requests

WEBHOOK = os.environ.get("TEAMS_WEBHOOK_URL")


def send(lines: Iterable[str]) -> None:
    if not WEBHOOK:
        return
    text = "\n".join(lines)
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "summary": "FinOps Report",
        "themeColor": "0076D7",
        "text": text,
    }
    resp = requests.post(WEBHOOK, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=10)
    resp.raise_for_status()


def main() -> None:
    send(sys.stdin.read().splitlines())


if __name__ == "__main__":
    main()
