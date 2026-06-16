
#!/usr/bin/env python3
"""Check Azure Budgets and send notifications to Slack/Teams."""

from __future__ import annotations

import os
import subprocess

import requests
from azure.identity import ClientSecretCredential
from azure.mgmt.consumption import ConsumptionManagementClient

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL")
TENANT_ID = os.environ["AZURE_TENANT_ID"]
CLIENT_ID = os.environ["AZURE_CLIENT_ID"]
CLIENT_SECRET = os.environ["AZURE_CLIENT_SECRET"]
SUBSCRIPTION_ID = os.environ["AZURE_SUBSCRIPTION_ID"]
BUDGET_NAMES = [name.strip() for name in os.environ.get("AZURE_BUDGET_NAMES", "").split(",") if name.strip()]


def notify(text: str) -> None:
    if SLACK_WEBHOOK_URL:
        resp = requests.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=10)
        resp.raise_for_status()
    if TEAMS_WEBHOOK_URL:
        subprocess.run(
            ["python", "scripts/finops/teams_notify.py"],
            input=text,
            text=True,
            check=True,
            env={**os.environ, "TEAMS_WEBHOOK_URL": TEAMS_WEBHOOK_URL},
        )


def main() -> None:
    if not BUDGET_NAMES:
        raise RuntimeError("AZURE_BUDGET_NAMES must list at least one budget")

    credential = ClientSecretCredential(TENANT_ID, CLIENT_ID, CLIENT_SECRET)
    client = ConsumptionManagementClient(credential, SUBSCRIPTION_ID)

    for name in BUDGET_NAMES:
        budget = client.budgets.get(scope=f"subscriptions/{SUBSCRIPTION_ID}", budget_name=name)
        actual = float(budget.current_spend.amount)
        forecast = float(budget.forecast_spend.amount or 0)
        limit = float(budget.amount)
        if forecast > limit:
            notify(f"*Azure Budget Alert* `{name}` forecast ${forecast:.2f} exceeds limit ${limit:.2f}")
        else:
            notify(f"Azure budget `{name}` OK. Actual ${actual:.2f}, forecast ${forecast:.2f}, limit ${limit:.2f}")


if __name__ == "__main__":
    main()
