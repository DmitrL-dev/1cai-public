
#!/usr/bin/env python3
"""
Wrapper around alkoleft/platform-context-exporter.

The external tool is not bundled: install it manually and set the environment
variable `PLATFORM_CONTEXT_EXPORTER_CMD` to the invocation string, e.g.:

    export PLATFORM_CONTEXT_EXPORTER_CMD="java -jar tools/platform-context-exporter.jar"

Usage:
    python scripts/context/export_platform_context.py \
        --config 1c_configurations/DO \
        --output output/context/platform_context.json
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

DEFAULT_CONFIG = Path("1c_configurations/DO")
DEFAULT_OUTPUT = Path("output/context/platform_context.json")


def resolve_command() -> list[str] | None:
    cmd = os.getenv("PLATFORM_CONTEXT_EXPORTER_CMD")
    if not cmd:
        print(
            "[export_context] PLATFORM_CONTEXT_EXPORTER_CMD is not set. "
            "Install https://github.com/alkoleft/platform-context-exporter and "
            "export the command (e.g. 'java -jar tools/platform-context-exporter.jar')."
        )
        return None
    return shlex.split(cmd)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export platform context via platform-context-exporter.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to configuration/workspace (default: 1c_configurations/DO)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON/ZIP path (default: output/context/platform_context.json)",
    )
    parser.add_argument(
        "--additional-args",
        nargs=argparse.REMAINDER,
        help="Additional arguments passed to the exporter.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    command = resolve_command()
    if not command:
        # Graceful exit, instructions already printed
        return 0

    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    invocation = command + [
        "--workspace",
        str(args.config),
        "--output",
        str(output_path),
    ]
    if args.additional_args:
        invocation.extend(args.additional_args)

    print("[export_context] Running:", " ".join(invocation))
    try:
        subprocess.run(invocation, check=True)
    except FileNotFoundError as exc:
        print(f"[export_context] Exporter command not found: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"[export_context] Export failed with code {exc.returncode}")
        return exc.returncode

    print(f"[export_context] Context exported to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

