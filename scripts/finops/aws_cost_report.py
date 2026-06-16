
#!/usr/bin/env python3
"""AWS Cost Explorer quick report (daily spend)."""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict

import boto3


def main() -> None:
    client = boto3.client("ce", region_name=os.getenv("AWS_REGION", "us-east-1"))

    end = dt.date.today()
    start = end - dt.timedelta(days=7)

    response: Dict[str, Any] = client.get_cost_and_usage(
        TimePeriod={
            "Start": start.isoformat(),
            "End": end.isoformat(),
        },
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
    )

    print("Date\tCost (USD)")
    for result in response["ResultsByTime"]:
        amount = result["Total"]["UnblendedCost"]["Amount"]
        date = result["TimePeriod"]["Start"]
        print(f"{date}\t${float(amount):.2f}")


if __name__ == "__main__":
    main()
