
#!/usr/bin/env python3
"""
Create release notes and optional git tag for a new version.

Usage:
    python scripts/release/create_release.py --version v5.2.0
        Generates RELEASE_NOTES.md (appends new section) based on commits since last tag.

    python scripts/release/create_release.py --version v5.2.0 --tag --push
        Additionally creates annotated git tag and pushes it to origin.

Assumptions:
    - Repository uses semantic version tags prefixed with "v".
    - Release notes are stored in RELEASE_NOTES.md (tracked).
"""

from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

RELEASE_NOTES_FILE = Path("RELEASE_NOTES.md")


def run_git(args: List[str]) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def get_last_tag() -> str | None:
    try:
        return run_git(["describe", "--tags", "--abbrev=0"])
    except subprocess.CalledProcessError:
        return None


def get_commits_since(tag: str | None) -> List[Tuple[str, str, str]]:
    """Return list of commits as (hash, author, subject)."""
    rev_range = f"{tag}..HEAD" if tag else "HEAD"
    log_format = "%h%x09%an%x09%s"
    output = run_git(["log", rev_range, "--pretty=format:" + log_format])
    if not output:
        return []
    commits = []
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            commits.append(tuple(parts))
    return commits


def write_release_notes(version: str, commits: List[Tuple[str, str, str]], append_existing: bool = True) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    header = f"## {version} — {today}\n"

    if not commits:
        body = "- No changes recorded (no commits since previous tag).\n"
    else:
        body_lines = [f"- {subject} ({commit} — {author})" for commit, author, subject in commits]
        body = "\n".join(body_lines) + "\n"

    content = header + "\n" + body + "\n"

    if append_existing and RELEASE_NOTES_FILE.exists():
        previous = RELEASE_NOTES_FILE.read_text(encoding="utf-8")
        RELEASE_NOTES_FILE.write_text(content + previous, encoding="utf-8")
    else:
        RELEASE_NOTES_FILE.write_text(content, encoding="utf-8")


def create_tag(version: str, message: str) -> None:
    run_git(["tag", "-a", version, "-m", message])


def push_tag(version: str) -> None:
    run_git(["push", "origin", version])


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate release notes and optional git tag.")
    parser.add_argument("--version", required=True, help="Target release version (e.g. v5.2.0)")
    parser.add_argument(
        "--no-append",
        action="store_true",
        help="Overwrite RELEASE_NOTES.md instead of prepending (default: prepend).",
    )
    parser.add_argument(
        "--tag",
        action="store_true",
        help="Create annotated git tag after generating release notes.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push created tag to origin (implies --tag).",
    )
    parser.add_argument(
        "--message",
        default=None,
        help="Custom tag message (default: 'Release <version>').",
    )

    args = parser.parse_args()

    previous_tag = get_last_tag()
    commits = get_commits_since(previous_tag)
    write_release_notes(args.version, commits, append_existing=not args.no_append)

    print(f"[release] Release notes updated in {RELEASE_NOTES_FILE}")
    if previous_tag:
        print(f"[release] Previous tag: {previous_tag}")
    print(f"[release] Commits included: {len(commits)}")

    if args.tag or args.push:
        message = args.message or f"Release {args.version}"
        create_tag(args.version, message)
        print(f"[release] Created tag {args.version}")
        if args.push:
            push_tag(args.version)
            print(f"[release] Pushed tag {args.version} to origin")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


