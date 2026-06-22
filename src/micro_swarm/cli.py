"""CLI for BSL code review via Go scanner + Micro-Model Swarm.

Usage:
    python -m src.micro_swarm.cli /path/to/project

Exit codes:
    0 — all files clean or handled by templates
    1 — some files require LLM review
    2 — scanner error
"""

from __future__ import annotations

import sys
from typing import Sequence

from src.micro_swarm.go_bridge import BridgeResult, GoBridge


def format_report(results: Sequence[BridgeResult]) -> str:
    """Format scan results as Russian text report.

    Args:
        results: list of BridgeResult from GoBridge.scan_and_review()

    Returns:
        Human-readable Russian report string
    """
    if not results:
        return "📋 BSL Review: 0 файлов проанализировано.\n"

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("📋 BSL Review — отчёт Micro-Model Swarm")
    lines.append("=" * 60)
    lines.append("")

    clean_count = 0
    template_count = 0
    llm_count = 0
    total_loc = 0

    for r in results:
        total_loc += r.loc

        if r.decision == "clean":
            clean_count += 1
            lines.append(f"  ✅ {r.path} ({r.loc} LOC) — чисто")
        elif r.decision == "template":
            template_count += 1
            lines.append(f"  🔶 {r.path} ({r.loc} LOC) — шаблонный ответ")
            if r.response:
                for resp_line in r.response.split("\n"):
                    lines.append(f"     {resp_line}")
        elif r.decision == "llm_required":
            llm_count += 1
            lines.append(f"  🔴 {r.path} ({r.loc} LOC) — требуется LLM ревью")

    # Summary
    lines.append("")
    lines.append("-" * 60)
    handled = clean_count + template_count
    total = len(results)
    savings_pct = round(handled / max(total, 1) * 100, 1)

    lines.append(f"Всего: {total} файлов, {total_loc} LOC")
    lines.append(f"  ✅ Чисто: {clean_count}")
    lines.append(f"  🔶 Шаблон: {template_count}")
    lines.append(f"  🔴 LLM: {llm_count}")
    lines.append(f"  💰 Экономия LLM: {savings_pct}%")
    lines.append("-" * 60)

    return "\n".join(lines) + "\n"


def run_bsl_review(path: str) -> int:
    """Run BSL review and print report.

    Args:
        path: path to 1C project directory

    Returns:
        Exit code: 0 = ok, 1 = llm needed, 2 = error
    """
    try:
        bridge = GoBridge()
        results = bridge.scan_and_review(path)
    except Exception as exc:
        print(f"❌ Ошибка сканирования: {exc}", file=sys.stderr)
        return 2

    report = format_report(results)
    print(report)

    has_llm = any(r.decision == "llm_required" for r in results)
    return 1 if has_llm else 0


def main() -> None:
    """CLI entrypoint."""
    if len(sys.argv) < 2:
        print("Использование: python -m src.micro_swarm.cli <путь>", file=sys.stderr)
        sys.exit(2)

    path = sys.argv[1]
    exit_code = run_bsl_review(path)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
