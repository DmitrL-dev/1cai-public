
#!/usr/bin/env python3
"""Запуск полного цикла аудит-проверок проекта."""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable


@dataclass
class AuditCommand:
    name: str
    command: List[str]
    required: bool = True


AUDITS: List[AuditCommand] = [
    AuditCommand("Markdown links", [PYTHON, "check_all_links.py"]),
    AuditCommand(
        "Comprehensive project audit",
        [PYTHON, "comprehensive_project_audit_final.py"],
    ),
    AuditCommand(
        "Security audit",
        [PYTHON, "check_security_comprehensive.py"],
    ),
    AuditCommand(
        "README vs Code",
        [PYTHON, "check_readme_vs_code.py"],
    ),
]

CLEANUP_COMMAND = AuditCommand(
    "Cleanup temporary reports",
    [PYTHON, "cleanup_all_temp.py"],
    required=False,
)


def run(cmd: AuditCommand, stop_on_failure: bool, verbose: bool) -> bool:
    print(f"\n=== {cmd.name} ===")
    if verbose:
        print("Command:", " ".join(cmd.command))

    try:
        result = subprocess.run(cmd.command, cwd=ROOT, check=False)
    except FileNotFoundError:
        print(f"[ERROR] Script not found: {cmd.command[-1]}")
        return False

    if result.returncode == 0:
        print(f"[OK] {cmd.name}")
        return True

    print(f"[FAIL] {cmd.name} (exit code {result.returncode})")
    if stop_on_failure and cmd.required:
        raise SystemExit(result.returncode)
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Запуск всех аудит-проверок проекта",
    )
    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Остановиться при первой ошибке",
    )
    parser.add_argument(
        "--include-cleanup",
        action="store_true",
        help="После аудитов запустить очистку временных файлов",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Показывать выполняемые команды",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print("=" * 80)
    print("FULL PROJECT AUDIT")
    print("=" * 80)

    results = []
    for audit in AUDITS:
        succeeded = run(audit, args.stop_on_failure, args.verbose)
        results.append((audit.name, succeeded))

    if args.include_cleanup:
        run(CLEANUP_COMMAND, False, args.verbose)

    print("\nSUMMARY")
    print("-" * 80)
    failures = 0
    for name, success in results:
        status = "OK" if success else "FAIL"
        print(f"{status:>4}  {name}")
        if not success:
            failures += 1

    if failures:
        print(f"\nCompleted with {failures} failure(s).")
        return 1

    print("\nAll audits completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

