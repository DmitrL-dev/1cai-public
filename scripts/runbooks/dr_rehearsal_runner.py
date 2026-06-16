
#!/usr/bin/env python3
"""Automate DR rehearsal steps for staging cluster."""
from __future__ import annotations

import argparse
import subprocess

COMMANDS = {
    "vault": [
        ["kubectl", "scale", "deploy", "vault", "--replicas=0", "-n", "vault"],
        ["kubectl", "scale", "deploy", "vault", "--replicas=1", "-n", "vault"],
        ["make", "vault-test"],
    ],
    "linkerd": [
        ["kubectl", "delete", "ns", "linkerd"],
        ["make", "linkerd-install"],
        ["kubectl", "annotate", "ns", "1cai", "linkerd.io/inject=enabled", "--overwrite"],
    ],
    "finops": [
        ["make", "finops-slack"],
    ],
}


def run_commands(name: str) -> None:
    for cmd in COMMANDS[name]:
        print(f"[dr] running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DR rehearsal step")
    parser.add_argument("component", choices=COMMANDS.keys())
    args = parser.parse_args()
    run_commands(args.component)


if __name__ == "__main__":
    main()
