
#!/usr/bin/env python3
"""Quick health check for bsl-language-server.

Usage::

    python scripts/parsers/check_bsl_language_server.py

The script will:

1. Resolve the BSL language server URL from the environment variable
   ``BSL_LANGUAGE_SERVER_URL`` (defaults to ``http://localhost:8080``).
2. Call ``/actuator/health`` and ensure the service reports ``{"status": "UP"}``.
3. Send a tiny ``textDocument/parse`` request to confirm AST parsing works.

If something fails, the script prints troubleshooting hints so the user can
investigate before escalating.
"""

from __future__ import annotations

import os
import sys
from textwrap import dedent

import requests

DEFAULT_URL = "http://localhost:8080"
HEALTH_ENDPOINT = "/actuator/health"
PARSE_ENDPOINT = "/lsp/parse"
TEST_SNIPPET = dedent(
    """
    #Область Служебные
    Процедура Тест()
    КонецПроцедуры
    #КонецОбласти
    """
)


def resolve_url() -> str:
    url = os.getenv("BSL_LANGUAGE_SERVER_URL", DEFAULT_URL)
    return url.rstrip("/")


def check_health(url: str) -> None:
    response = requests.get(f"{url}{HEALTH_ENDPOINT}", timeout=5)
    response.raise_for_status()
    data = response.json()
    if data.get("status") != "UP":
        raise RuntimeError(f"Unexpected health status: {data}")


def check_parse(url: str) -> None:
    payload = {
        "text": TEST_SNIPPET,
        "uri": "untitled:test.bsl",
        "languageId": "bsl",
    }
    response = requests.post(f"{url}{PARSE_ENDPOINT}", json=payload, timeout=10)
    response.raise_for_status()
    data = response.json()
    if "ast" not in data:
        raise RuntimeError("Server responded without 'ast' field")


def main() -> int:
    url = resolve_url()
    print(f"[bsl-ls-check] Checking bsl-language-server at {url}")

    try:
        check_health(url)
        print("  ✅ Health endpoint returned status=UP")
    except Exception as exc:  # noqa: BLE001 - we want to surface any issue
        print("  ❌ Health check failed:", exc)
        print("    - Ensure the service is running (e.g. 'make bsl-ls-up')")
        print("    - If running outside Docker, verify firewall/port forwarding")
        return 1

    try:
        check_parse(url)
        print("  ✅ Parse endpoint returned AST payload")
    except Exception as exc:  # noqa: BLE001
        print("  ❌ Parse request failed:", exc)
        print("    - Check service logs: 'make bsl-ls-logs'")
        print("    - Verify image version (ghcr.io/1c-syntax/bsl-language-server)")
        print("    - Ensure requests reach the correct base URL")
        return 1

    print("[bsl-ls-check] All checks passed.")
    print("  Tip: export BSL_LANGUAGE_SERVER_URL to test different instances.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
