
#!/usr/bin/env python3
"""Send AWS cost report to Slack webhook (and optionally Teams)."""

from __future__ import annotations

import datetime as dt
import os
import subprocess
from typing import Dict

import boto3
import requests

WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL")


def fetch_costs(days: int = 3) -> Dict[str, float]:
    client = boto3.client("ce", region_name=os.getenv("AWS_REGION", "us-east-1"))
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    response = client.get_cost_and_usage(
        TimePeriod={
            "Start": start.isoformat(),
            "End": end.isoformat(),
        },
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
    )
    return {
        item["TimePeriod"]["Start"]: float(item["Total"]["UnblendedCost"]["Amount"])
        for item in response["ResultsByTime"]
    }


def build_lines(costs: Dict[str, float]) -> str:
    lines = [f"• {date}: ${amount:.2f}" for date, amount in sorted(costs.items())]
    return "AWS Cost Report (last 3 days)\n" + "\n".join(lines)


def post_to_slack(text: str) -> None:
    if not WEBHOOK_URL:
        return
    resp = requests.post(WEBHOOK_URL, json={"text": text}, timeout=10)
    resp.raise_for_status()


def post_to_teams(text: str) -> None:
    if not TEAMS_WEBHOOK_URL:
        return
    subprocess.run(
        ["python", "scripts/finops/teams_notify.py"],
        input=text,
        text=True,
        check=True,
        env={**os.environ, "TEAMS_WEBHOOK_URL": TEAMS_WEBHOOK_URL},
    )


def main() -> None:
    costs = fetch_costs()
    text = build_lines(costs)
    post_to_slack(text)
    post_to_teams(text)


if __name__ == "__main__":
    main()
