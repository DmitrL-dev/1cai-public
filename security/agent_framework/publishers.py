
"""Utilities for publishing reports to external systems."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import httpx

try:
    import boto3
    from botocore.config import Config as BotoConfig
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]
    BotoConfig = object  # type: ignore[misc, assignment]


class S3PublishError(RuntimeError):
    """Raised when uploading reports to S3 fails."""


class ConfluencePublishError(RuntimeError):
    """Raised when publishing to Confluence fails."""


def upload_to_s3(  # pragma: no cover - exercised via tests with monkeypatch
    bucket: str,
    *,
    html_path: Path,
    md_path: Path,
    prefix: Optional[str] = None,
    region: Optional[str] = None,
    endpoint: Optional[str] = None,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
) -> None:
    if boto3 is None:
        raise S3PublishError("boto3 is required for S3 upload but is not installed.")

    session_kwargs = {}
    if access_key and secret_key:
        session_kwargs.update(
            {"aws_access_key_id": access_key, "aws_secret_access_key": secret_key}
        )

    session = boto3.session.Session(region_name=region, **session_kwargs)  # type: ignore[arg-type]
    config = BotoConfig(signature_version="s3v4") if endpoint else None
    client_kwargs = {"config": config} if config else {}
    if endpoint:
        client_kwargs["endpoint_url"] = endpoint

    s3 = session.client("s3", **client_kwargs)
    base_key = prefix.rstrip("/") + "/" if prefix else ""

    for path in (html_path, md_path):
        key = f"{base_key}{path.name}"
        try:
            s3.upload_file(str(path), bucket, key)
        except Exception as exc:  # pragma: no cover - boto specific exceptions
            raise S3PublishError(f"Failed to upload {path.name} to s3://{bucket}/{key}: {exc}") from exc


def publish_to_confluence(
    *,
    url: str,
    user: str,
    token: str,
    space: str,
    parent_id: Optional[str],
    title: str,
    html_content: str,
) -> str:
    page_data = {
        "type": "page",
        "title": title,
        "space": {"key": space},
        "body": {
            "storage": {
                "value": html_content,
                "representation": "storage",
            }
        },
    }
    if parent_id:
        page_data["ancestors"] = [{"id": parent_id}]

    api_url = f"{url.rstrip('/')}/rest/api/content"
    response = httpx.post(
        api_url,
        json=page_data,
        auth=(user, token),
        timeout=10.0,
    )
    if response.status_code >= 300:
        raise ConfluencePublishError(
            f"Confluence responded with {response.status_code}: {response.text}"
        )
    data = response.json()
    return data.get("_links", {}).get("base", url.rstrip("/")) + data.get("_links", {}).get("webui", "")


def send_ticket_webhook(
    *,
    webhook_url: str,
    tickets: list[dict],
) -> None:
    if not tickets:
        return
    response = httpx.post(
        webhook_url,
        json={"tickets": tickets},
        timeout=10.0,
    )
    if response.status_code >= 300:
        raise RuntimeError(f"Ticket webhook failed with {response.status_code}: {response.text}")

