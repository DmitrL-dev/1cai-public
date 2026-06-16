
#!/usr/bin/env python3
"""Send Azure Cost Management report to Slack/Teams."""

from __future__ import annotations

import datetime as dt
import os
import subprocess
from typing import Dict

import requests
from azure.identity import ClientSecretCredential
from azure.mgmt.costmanagement import CostManagementClient

WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL")
TENANT_ID = os.environ["AZURE_TENANT_ID"]
CLIENT_ID = os.environ["AZURE_CLIENT_ID"]
CLIENT_SECRET = os.environ["AZURE_CLIENT_SECRET"]
SUBSCRIPTION_ID = os.environ["AZURE_SUBSCRIPTION_ID"]


def fetch_costs(days: int = 3) -> Dict[str, float]:
    credential = ClientSecretCredential(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
    )
    client = CostManagementClient(credential)

    end = dt.date.today()
    start = end - dt.timedelta(days=days)

    report = client.query.usage(
        scope=f"subscriptions/{SUBSCRIPTION_ID}",
        parameters={
            "type": "Usage",
            "timeframe": "Custom",
            "timePeriod": {
                "from": dt.datetime.combine(start, dt.time.min).isoformat(),
                "to": dt.datetime.combine(end, dt.time.min).isoformat(),
            },
            "dataset": {
                "granularity": "Daily",
                "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}},
            },
        },
    )

    results: Dict[str, float] = {}
    for row in report.rows:  # type: ignore[attr-defined]
        date = row[0]
        amount = float(row[1])
        results[date] = amount
    return results


def build_lines(costs: Dict[str, float]) -> str:
    lines = [f"• {date}: ${amount:.2f}" for date, amount in sorted(costs.items())]
    return "Azure Cost Report (last 3 days)\n" + "\n".join(lines)


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
