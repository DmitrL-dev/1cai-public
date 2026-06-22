"""Local CI/release gate for 1cAI Рентген.

Examples:
  C:\Python311\python.exe tools\rentgen\ci_gate.py --module CommonModules/X/Ext/Module.bsl
  C:\Python311\python.exe tools\rentgen\ci_gate.py --diff-file changes.diff --markdown report.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from store import get_store  # noqa: E402

from src.services.rentgen.change_plan import (  # noqa: E402
    assess_ci_gate,
    build_change_plan,
    extract_diff_modules,
    render_markdown_report,
)


def _read_diff(args: argparse.Namespace) -> str | None:
    if args.diff_file:
        return Path(args.diff_file).read_text(encoding="utf-8")
    if args.diff_stdin:
        return sys.stdin.read()
    return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze 1C changed modules with Рентген and return CI gate status.",
    )
    parser.add_argument(
        "--module",
        action="append",
        default=[],
        help="Changed BSL module path. Can be repeated.",
    )
    parser.add_argument(
        "--modules-file", help="Text file with one changed module path per line."
    )
    parser.add_argument(
        "--diff-file", help="Unified diff file to parse for changed .bsl modules."
    )
    parser.add_argument(
        "--diff-stdin", action="store_true", help="Read unified diff from stdin."
    )
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument("--max-edges", type=int, default=600)
    parser.add_argument("--hotspot-limit", type=int, default=10)
    parser.add_argument("--risk-threshold", type=int, default=70)
    parser.add_argument("--impact-threshold", type=int, default=300)
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Return exit code 0 even with violations.",
    )
    parser.add_argument(
        "--json", dest="json_path", help="Write JSON report to this path."
    )
    parser.add_argument("--markdown", help="Write markdown report to this path.")
    parser.add_argument(
        "--quiet", action="store_true", help="Do not print markdown to stdout."
    )
    return parser.parse_args()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    args = _parse_args()
    modules = list(args.module)
    if args.modules_file:
        modules.extend(
            line.strip()
            for line in Path(args.modules_file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    modules.extend(extract_diff_modules(_read_diff(args)))

    if not modules:
        print(
            "No changed .bsl modules found. Provide --module, --modules-file, --diff-file or --diff-stdin.",
            file=sys.stderr,
        )
        return 2

    store = get_store()
    plan = build_change_plan(
        store,
        modules,
        max_depth=args.max_depth,
        max_edges=args.max_edges,
        hotspot_limit=args.hotspot_limit,
    )
    gate = assess_ci_gate(
        plan,
        risk_threshold=args.risk_threshold,
        impact_threshold=args.impact_threshold,
        fail_on_high=not args.warn_only,
    )
    report = {"gate": gate, "plan": plan}
    markdown = render_markdown_report(plan, gate)

    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if args.markdown:
        Path(args.markdown).write_text(markdown, encoding="utf-8")

    if not args.quiet:
        print(markdown)
    if gate["status"] == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
