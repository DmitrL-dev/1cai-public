
#!/usr/bin/env python3
"""
Minimal GitHub repository monitor for external dependencies.

Reads the current state of selected repositories (latest release, head commit)
and stores the snapshot in `output/monitoring/github_state.json` by default.
If differences with the previous snapshot are detected, they are printed to stdout.

Usage:
    python scripts/monitoring/github_monitor.py              # check default repos
    python scripts/monitoring/github_monitor.py --repo owner/name
    python scripts/monitoring/github_monitor.py --output output/monitoring/custom.json

Environment variables:
    GITHUB_TOKEN or GH_TOKEN — optional, increases rate limits for API calls.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import httpx

DEFAULT_REPOS: Tuple[str, ...] = (
    "1c-syntax/bsl-language-server",
    "1c-syntax/tree-sitter-bsl",
    "alkoleft/platform-context-exporter",
    "alkoleft/ones_doc_gen",
    "alkoleft/yaxunit",
    "alkoleft/mcp-onec-test-runner",
    "alkoleft/cfg_tools",
    "alkoleft/metadata.js",
)

DEFAULT_OUTPUT = Path("output/monitoring/github_state.json")


@dataclass
class RepoState:
    repository: str
    checked_at: str
    default_branch: Optional[str]
    latest_commit: Optional[str]
    latest_release: Optional[str]

    @classmethod
    def from_api(cls, repository: str, repo_payload: Dict, commit_sha: Optional[str], release_tag: Optional[str]) -> "RepoState":
        return cls(
            repository=repository,
            checked_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            default_branch=repo_payload.get("default_branch"),
            latest_commit=commit_sha,
            latest_release=release_tag,
        )


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor GitHub repositories for new releases and commits.")
    parser.add_argument(
        "--repo",
        dest="repos",
        action="append",
        help="Repository in owner/name format. Can be used multiple times. Defaults to curated list.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Path to store monitoring state (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not write the state file, only print the summary.",
    )
    return parser.parse_args(list(argv))


def load_previous_state(path: Path) -> Dict[str, RepoState]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        result: Dict[str, RepoState] = {}
        for item in payload:
            if not isinstance(item, dict) or "repository" not in item:
                continue
            result[item["repository"]] = RepoState(
                repository=item.get("repository", ""),
                checked_at=item.get("checked_at", ""),
                default_branch=item.get("default_branch"),
                latest_commit=item.get("latest_commit"),
                latest_release=item.get("latest_release"),
            )
        return result
    except json.JSONDecodeError as exc:
        print(f"[github_monitor] Failed to read previous state ({exc}). Ignoring file.", file=sys.stderr)
        return {}


def save_state(path: Path, states: List[RepoState]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = [asdict(state) for state in states]
    path.write_text(json.dumps(serialized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[github_monitor] State written to {path}")


def resolve_token() -> Optional[str]:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        return token.strip()
    return None


def build_client(token: Optional[str]) -> httpx.Client:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "1c-ai-stack-monitor/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url="https://api.github.com", headers=headers, timeout=httpx.Timeout(10.0, connect=5.0))


def fetch_repo_payload(client: httpx.Client, repository: str) -> Dict:
    response = client.get(f"/repos/{repository}")
    response.raise_for_status()
    return response.json()


def fetch_commit_sha(client: httpx.Client, repository: str, branch: Optional[str]) -> Optional[str]:
    if not branch:
        return None
    response = client.get(f"/repos/{repository}/commits/{branch}")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    return payload.get("sha")


def fetch_latest_release(client: httpx.Client, repository: str) -> Optional[str]:
    response = client.get(f"/repos/{repository}/releases/latest")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    return payload.get("tag_name")


def compare_states(previous: Dict[str, RepoState], current: RepoState) -> List[str]:
    messages: List[str] = []
    old = previous.get(current.repository)
    if not old:
        messages.append(f"[github_monitor] NEW repo tracked: {current.repository}")
        if current.latest_release:
            messages.append(f"  • Latest release → {current.latest_release}")
        if current.latest_commit:
            messages.append(f"  • Latest commit  → {current.latest_commit}")
        return messages

    if current.latest_release and current.latest_release != old.latest_release:
        messages.append(
            f"[github_monitor] Release update for {current.repository}: {old.latest_release!r} → {current.latest_release!r}"
        )
    if current.latest_commit and current.latest_commit != old.latest_commit:
        messages.append(
            f"[github_monitor] Commit update for {current.repository}: {old.latest_commit!r} → {current.latest_commit!r}"
        )
    return messages


def monitor_repositories(repos: Iterable[str], output: Path, save: bool) -> int:
    token = resolve_token()
    with build_client(token) as client:
        previous = load_previous_state(output)
        collected: List[RepoState] = []
        total_messages: List[str] = []

        for repository in repos:
            try:
                repo_payload = fetch_repo_payload(client, repository)
                default_branch = repo_payload.get("default_branch")
                commit_sha = fetch_commit_sha(client, repository, default_branch)
                release_tag = fetch_latest_release(client, repository)
                state = RepoState.from_api(repository, repo_payload, commit_sha, release_tag)
                collected.append(state)
                total_messages.extend(compare_states(previous, state))
                print(
                    f"[github_monitor] {repository}: branch={default_branch!r}, commit={commit_sha!r}, release={release_tag!r}"
                )
            except httpx.HTTPStatusError as exc:
                print(f"[github_monitor] HTTP error while fetching {repository}: {exc.response.status_code} {exc}", file=sys.stderr)
            except httpx.HTTPError as exc:
                print(f"[github_monitor] Network error for {repository}: {exc}", file=sys.stderr)

        if total_messages:
            print("\n".join(total_messages))
        else:
            print("[github_monitor] No changes detected.")

        if not save:
            return 0
        save_state(output, collected)
    return 0


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    repos = args.repos if args.repos else list(DEFAULT_REPOS)
    if not repos:
        print("[github_monitor] No repositories to monitor.", file=sys.stderr)
        return 1
    return monitor_repositories(repos, args.output, save=not args.no_save)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


