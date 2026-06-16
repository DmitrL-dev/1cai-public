
#!/usr/bin/env python3
"""
Collect weekly DORA metrics based on git tags and history.

Metrics (approximation):
    - deployment_frequency: number of tags (v*) created within period / weeks
    - lead_time_hours: average time from commit authored to release tag timestamp
    - change_failure_rate: ratio of releases within period containing "hotfix" or "fix" in tag message (heuristic)
    - mean_time_to_restore_hours: average time between failure-tag and next release

Outputs JSON and Markdown summaries in output/metrics/.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

OUTPUT_DIR = Path("output/metrics")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
STATUS_DIR = Path("docs/status")
STATUS_DIR.mkdir(parents=True, exist_ok=True)


def run_git(args: List[str]) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def list_tags() -> List[str]:
    try:
        tags = run_git(["for-each-ref", "--format=%(refname:strip=2)", "--sort=creatordate", "refs/tags/v*"])
        return [tag for tag in tags.splitlines() if tag]
    except subprocess.CalledProcessError:
        return []


def tag_timestamp(tag: str) -> datetime:
    ts = run_git(["show", "-s", "--format=%ct", tag])
    return datetime.fromtimestamp(int(ts), tz=timezone.utc)


def tag_message(tag: str) -> str:
    try:
        return run_git(["tag", "-l", tag, "--format=%(contents)"])
    except subprocess.CalledProcessError:
        return ""


def commits_between(start: Optional[str], end: str) -> List[str]:
    rev_range = f"{start}..{end}" if start else end
    logs = run_git(["rev-list", rev_range])
    if not logs:
        return []
    return logs.splitlines()


def commit_timestamp(commit: str) -> datetime:
    ts = run_git(["show", "-s", "--format=%ct", commit])
    return datetime.fromtimestamp(int(ts), tz=timezone.utc)


def compute_metrics(period_days: int) -> Dict[str, float]:
    tags = list_tags()
    if not tags:
        return {
            "deployment_frequency": 0.0,
            "lead_time_hours": 0.0,
            "change_failure_rate": 0.0,
            "mean_time_to_restore_hours": 0.0,
        }

    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=period_days)

    releases_in_period: List[str] = []
    release_times: Dict[str, datetime] = {}
    for tag in tags:
        ts = tag_timestamp(tag)
        release_times[tag] = ts
        if ts >= period_start:
            releases_in_period.append(tag)

    if not releases_in_period:
        return {
            "deployment_frequency": 0.0,
            "lead_time_hours": 0.0,
            "change_failure_rate": 0.0,
            "mean_time_to_restore_hours": 0.0,
        }

    deployments_per_week = len(releases_in_period) / (period_days / 7.0)

    lead_times: List[float] = []
    failure_tags: List[str] = []

    for idx, tag in enumerate(releases_in_period):
        previous_tag = None
        full_index = tags.index(tag)
        if full_index > 0:
            previous_tag = tags[full_index - 1]

        commits = commits_between(previous_tag, tag)
        if commits:
            release_time = release_times[tag]
            for commit in commits:
                commit_time = commit_timestamp(commit)
                lead_hours = (release_time - commit_time).total_seconds() / 3600.0
                if lead_hours >= 0:
                    lead_times.append(lead_hours)

        message = tag_message(tag).lower()
        if "hotfix" in message or "fix" in message:
            failure_tags.append(tag)

    average_lead = sum(lead_times) / len(lead_times) if lead_times else 0.0

    change_failure_rate = len(failure_tags) / len(releases_in_period) if releases_in_period else 0.0

    restore_times: List[float] = []
    for tag in failure_tags:
        index = tags.index(tag)
        if index + 1 < len(tags):
            next_tag = tags[index + 1]
            restore_time = (release_times[next_tag] - release_times[tag]).total_seconds() / 3600.0
            restore_times.append(max(restore_time, 0.0))
    mttr = sum(restore_times) / len(restore_times) if restore_times else 0.0

    return {
        "deployment_frequency": round(deployments_per_week, 2),
        "lead_time_hours": round(average_lead, 2),
        "change_failure_rate": round(change_failure_rate, 2),
        "mean_time_to_restore_hours": round(mttr, 2),
    }


def write_outputs(metrics: Dict[str, float], period_days: int) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
    json_payload = {
        "generated_at": timestamp,
        "period_days": period_days,
        "metrics": metrics,
    }
    json_path = OUTPUT_DIR / "dora_latest.json"
    json_path.write_text(json.dumps(json_payload, indent=2), encoding="utf-8")

    summary_path = OUTPUT_DIR / "dora_summary.md"
    summary_lines = [
        f"# DORA Metrics Summary ({timestamp})",
        f"- Period: last {period_days} day(s)",
        f"- Deployment frequency (per week): {metrics['deployment_frequency']}",
        f"- Lead time (hours): {metrics['lead_time_hours']}",
        f"- Change failure rate: {metrics['change_failure_rate']}",
        f"- MTTR (hours): {metrics['mean_time_to_restore_hours']}",
        "",
        "> Change failure rate и MTTR вычисляются по эвристике: релизы с \"fix\"/\"hotfix\" в описании считаются неудавшимися.",
    ]
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    history_path = STATUS_DIR / "dora_history.md"
    history_entry = [
        f"## {timestamp}",
        f"- Period: last {period_days} day(s)",
        f"- Deployment frequency (per week): {metrics['deployment_frequency']}",
        f"- Lead time (hours): {metrics['lead_time_hours']}",
        f"- Change failure rate: {metrics['change_failure_rate']}",
        f"- MTTR (hours): {metrics['mean_time_to_restore_hours']}",
        "",
    ]
    if history_path.exists():
        previous = history_path.read_text(encoding="utf-8")
        content = "\n".join(history_entry) + previous
    else:
        header = "# DORA Metrics History\n\n"
        content = header + "\n".join(history_entry)
    history_path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect DORA metrics based on git tags.")
    parser.add_argument("--period-days", type=int, default=7, help="Period in days to evaluate (default: 7).")
    args = parser.parse_args()

    metrics = compute_metrics(args.period_days)
    write_outputs(metrics, args.period_days)
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


