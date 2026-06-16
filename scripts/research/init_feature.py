
#!/usr/bin/env python3
"""
Initialize spec-driven feature workspace.

Creates `docs/research/features/<slug>/` with plan/spec/tasks/research documents
copied from templates and fills in metadata (title, date, owner placeholder).

Usage:
    python scripts/research/init_feature.py --slug bsl-language-server-integration
    python scripts/research/init_feature.py --slug new-feature --base-dir docs/research/features

By default, expects templates in `templates/`. Customize with `--templates`.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_BASE_DIR = Path("docs/research/features")
DEFAULT_TEMPLATES = Path("templates")

FILES = {
    "plan.md": "feature-plan.md",
    "spec.md": "feature-spec.md",
    "tasks.md": "feature-tasks.md",
    "research.md": "feature-research.md",
}


@dataclass(frozen=True)
class Context:
    slug: str
    feature_title: str
    date: str
    owner_placeholder: str = "{{OWNER}}"


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create spec-driven feature scaffold.")
    parser.add_argument("--slug", required=True, help="Feature slug (lowercase letters, digits, hyphen).")
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE_DIR,
        help=f"Base directory for features (default: {DEFAULT_BASE_DIR})",
    )
    parser.add_argument(
        "--templates",
        type=Path,
        default=DEFAULT_TEMPLATES,
        help=f"Templates directory (default: {DEFAULT_TEMPLATES})",
    )
    parser.add_argument(
        "--owner",
        default="{{OWNER}}",
        help="Owner placeholder to insert into tasks.md (default: '{{OWNER}}').",
    )
    return parser.parse_args(list(argv))


def validate_slug(slug: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9\-]*", slug):
        raise ValueError("Slug must contain lowercase letters, digits, hyphen, and start with alphanumeric.")


def slug_to_title(slug: str) -> str:
    parts = slug.replace("-", " ").split()
    return " ".join(word.capitalize() for word in parts)


def ensure_templates(templates_dir: Path) -> None:
    missing = [template for template in FILES.values() if not (templates_dir / template).exists()]
    if missing:
        raise FileNotFoundError(f"Missing template files: {', '.join(missing)} in {templates_dir}")


def render_template(content: str, context: Context, owner: str) -> str:
    rendered = content.replace("{{FEATURE_TITLE}}", context.feature_title).replace("{{DATE}}", context.date)
    if owner != "{{OWNER}}":
        rendered = rendered.replace("{{OWNER}}", owner)
    return rendered


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    try:
        validate_slug(args.slug)
    except ValueError as exc:
        print(f"[init_feature] Invalid slug: {exc}", file=sys.stderr)
        return 2

    try:
        ensure_templates(args.templates)
    except FileNotFoundError as exc:
        print(f"[init_feature] {exc}", file=sys.stderr)
        return 2

    target_dir = args.base_dir / args.slug
    if target_dir.exists():
        print(f"[init_feature] Target directory already exists: {target_dir}", file=sys.stderr)
        return 1

    context = Context(
        slug=args.slug,
        feature_title=slug_to_title(args.slug),
        date=_dt.date.today().isoformat(),
        owner_placeholder=args.owner,
    )

    target_dir.mkdir(parents=True, exist_ok=False)

    for filename, template_name in FILES.items():
        src = args.templates / template_name
        dst = target_dir / filename
        content = src.read_text(encoding="utf-8")
        rendered = render_template(content, context, owner=args.owner)
        dst.write_text(rendered, encoding="utf-8")
        print(f"[init_feature] Created {dst}")

    print(
        f"[init_feature] Feature scaffold created at {target_dir}. "
        "Fill in plan/spec/tasks/research and update documentation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


