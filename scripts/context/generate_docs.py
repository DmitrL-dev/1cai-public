
#!/usr/bin/env python3
"""
Wrapper around alkoleft/ones_doc_gen.

Set ONES_DOC_GEN_CMD to the executable command, e.g.:
    export ONES_DOC_GEN_CMD="oscript tools/ones_doc_gen/src/main.os"

Then run:
    python scripts/context/generate_docs.py --workspace 1c_configurations/DO \
        --output output/docs/generated
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

DEFAULT_WORKSPACE = Path("1c_configurations/DO")
DEFAULT_OUTPUT = Path("output/docs/generated")


def resolve_command() -> list[str] | None:
    cmd = os.getenv("ONES_DOC_GEN_CMD")
    if not cmd:
        print(
            "[generate_docs] ONES_DOC_GEN_CMD is not set. "
            "Install https://github.com/alkoleft/ones_doc_gen and export the command "
            "(e.g. 'oscript tools/ones_doc_gen/src/main.os')."
        )
        return None
    return shlex.split(cmd)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate documentation via ones_doc_gen.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=DEFAULT_WORKSPACE,
        help="Path to 1C workspace/configuration (default: 1c_configurations/DO)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output directory for generated docs (default: output/docs/generated)",
    )
    parser.add_argument(
        "--format",
        default="rst",
        help="Output format (depends on ones_doc_gen capabilities, default: rst)",
    )
    parser.add_argument(
        "--additional-args",
        nargs=argparse.REMAINDER,
        help="Additional args passed to ones_doc_gen.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    command = resolve_command()
    if not command:
        return 0

    output_dir: Path = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    invocation = command + [
        "--workspace",
        str(args.workspace),
        "--format",
        args.format,
        "--output",
        str(output_dir),
    ]
    if args.additional_args:
        invocation.extend(args.additional_args)

    print("[generate_docs] Running:", " ".join(invocation))
    try:
        subprocess.run(invocation, check=True)
    except FileNotFoundError as exc:
        print(f"[generate_docs] ones_doc_gen command not found: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"[generate_docs] Documentation generation failed with code {exc.returncode}")
        return exc.returncode

    print(f"[generate_docs] Documentation generated into {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

