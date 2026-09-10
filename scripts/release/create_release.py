"""Generate notes, then separately tag committed notes; pushing needs a named remote."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess

RELEASE_NOTES_FILE = Path("RELEASE_NOTES.md")
VERSION = re.compile(
    r"(?:(?:core|companion)-)?v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?"
)


def run_git(args):
    return subprocess.check_output(
        ["git", *args], text=True, encoding="utf-8", stderr=subprocess.PIPE
    ).strip()


def get_last_tag(version):
    family = version.split("v", 1)[0] + "v[0-9]*"
    try:
        return run_git(
            [
                "describe",
                "--tags",
                "--abbrev=0",
                "--match",
                family,
                "--exclude",
                version,
                "HEAD",
            ]
        )
    except subprocess.CalledProcessError:
        return None


def get_commits_since(tag):
    output = run_git(
        ["log", f"{tag}..HEAD" if tag else "HEAD", "--pretty=format:%h%x09%an%x09%s"]
    )
    return [
        tuple(line.split("\t", 2))
        for line in output.splitlines()
        if len(line.split("\t", 2)) == 3
    ]


def write_release_notes(version, commits, append_existing=True):
    previous = (
        RELEASE_NOTES_FILE.read_text("utf-8")
        if append_existing and RELEASE_NOTES_FILE.exists()
        else ""
    )
    pattern = re.compile(
        r"^## " + re.escape(version) + r" — [^\n]*\n.*?(?=^## |\Z)", re.M | re.S
    )
    existing = pattern.search(previous)
    header = (
        existing.group().splitlines()[0]
        if existing
        else f"## {version} — {datetime.now(timezone.utc):%Y-%m-%d}"
    )
    previous = pattern.sub("", previous)
    body = "\n".join(
        f"- {subject} ({commit} — {author})" for commit, author, subject in commits
    )
    body = body or "- No changes recorded since the previous tag."
    RELEASE_NOTES_FILE.write_text(
        header + "\n\n" + body + "\n\n" + previous, encoding="utf-8"
    )


def create_tag(version, message):
    if run_git(["status", "--porcelain=v1", "--untracked-files=normal"]):
        raise ValueError(
            "Tagging requires a clean worktree and committed release notes"
        )
    committed = run_git(["show", "HEAD:RELEASE_NOTES.md"])
    if not committed.startswith("## " + version + " — "):
        raise ValueError("Commit reviewed notes for this version before tagging")
    run_git(["tag", "-a", version, "-m", message])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--no-append", action="store_true")
    parser.add_argument(
        "--tag",
        action="store_true",
        help="Tag HEAD after separately committing reviewed notes",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Create the tag and push only that ref to --remote",
    )
    parser.add_argument(
        "--remote", help="Explicit configured remote; no implicit origin"
    )
    parser.add_argument("--message")
    args = parser.parse_args(argv)
    if not VERSION.fullmatch(args.version):
        parser.error("Expected a version such as v1.2.3 or companion-v0.1.4")
    if args.push and (
        not args.remote or args.remote not in run_git(["remote"]).splitlines()
    ):
        parser.error("Pushing requires an explicit configured --remote")
    if args.tag or args.push:
        create_tag(args.version, args.message or f"Release {args.version}")
        if args.push:
            ref = "refs/tags/" + args.version
            run_git(["push", args.remote, ref + ":" + ref])
        print(
            f"[release] Created tag {args.version}"
            + (f" and pushed to {args.remote}" if args.push else "")
        )
    else:
        previous = get_last_tag(args.version)
        commits = get_commits_since(previous)
        write_release_notes(args.version, commits, append_existing=not args.no_append)
        print(
            f"[release] Notes generated: {len(commits)} commits; previous tag: {previous or 'none'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
