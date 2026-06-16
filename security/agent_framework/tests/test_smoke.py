
"""Smoke tests for the security agent framework."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx

from security.agent_framework.cli.main import handle_local_run
from security.agent_framework.runtime import (AgentResult, Finding,
                                              SecurityAgent)


def make_client(response: httpx.Response) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return response

    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def test_agent_reports_missing_security_headers():
    response = httpx.Response(
        status_code=200,
        text="OK",
        headers={"Content-Type": "text/html"},
    )
    client = make_client(response)
    agent = SecurityAgent()

    try:
        result = agent.run("http://service.local", client=client)
    finally:
        client.close()

    missing_headers = {finding.title for finding in result.findings}
    assert "Отсутствует заголовок Content-Security-Policy" in missing_headers
    assert any("HTTP 200 OK" in note for note in result.notes)
    assert any("телеметрия" in note.lower() for note in result.notes)


def test_agent_handles_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    agent = SecurityAgent()

    try:
        result = agent.run("http://unreachable.local", client=client)
    finally:
        client.close()

    assert result.findings, "Expected at least one finding for unreachable target"
    assert result.findings[0].severity == "critical"


def test_repo_static_profile_detects_sensitive_files(tmp_path):
    secrets_dir = tmp_path / "project"
    secrets_dir.mkdir()
    (secrets_dir / ".env").write_text("API_KEY=1234567890", encoding="utf-8")
    (secrets_dir / "config.py").write_text("password = 'secretvalue123456'", encoding="utf-8")

    agent = SecurityAgent(profile="repo-static")
    result = agent.run(str(secrets_dir))

    titles = {finding.title for finding in result.findings}
    assert any("чувствительный файл" in title.lower() for title in titles)
    assert any("секрет" in title.lower() for title in titles)


def test_n8n_workflow_profile_detects_insecure_http(tmp_path):
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "name": "HTTP Request",
                        "type": "n8n-nodes-base.httpRequest",
                        "parameters": {
                            "url": "http://example.com/api",
                            "authentication": "none",
                            "ignoreSSLIssues": True
                        },
                        "credentials": None
                    },
                    {
                        "name": "Webhook In",
                        "type": "n8n-nodes-base.webhook",
                        "parameters": {
                            "path": "test",
                            "authentication": "none",
                            "responseMode": "onReceived"
                        },
                        "credentials": None
                    },
                    {
                        "name": "Function Check",
                        "type": "n8n-nodes-base.function",
                        "parameters": {
                            "functionCode": "const data = eval('1+1'); return [{ result: data }];"
                        },
                        "credentials": None
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    agent = SecurityAgent(profile="n8n-workflow")
    result = agent.run(str(workflow_path))
    titles = {finding.title for finding in result.findings}
    assert any("небезопасный url" in title.lower() for title in titles)
    assert any("webhook" in title.lower() for title in titles)
    assert any("function node" in title.lower() for title in titles)


def test_bsl_profile_detects_execute(tmp_path):
    bsl_path = tmp_path / "module.bsl"
    bsl_path.write_text("Процедура Тест()\n    Выполнить(\"Сообщить('test')\");\nКонецПроцедуры\n", encoding="utf-8")
    agent = SecurityAgent(profile="bsl-1c")
    result = agent.run(str(bsl_path))
    titles = {finding.title for finding in result.findings}
    assert any("опасное выполнение" in title.lower() for title in titles)


def test_bsl_privileged_mode(tmp_path):
    bsl_path = tmp_path / "module2.bsl"
    bsl_path.write_text(
        "Процедура Тест()\n    УстановитьПривилегированныйРежим(Истина);\nКонецПроцедуры\n", encoding="utf-8"
    )
    agent = SecurityAgent(profile="bsl-1c")
    result = agent.run(str(bsl_path))
    titles = {finding.title for finding in result.findings}
    assert any("привилегирован" in title.lower() for title in titles)


def test_cli_local_output(tmp_path, monkeypatch):
    output_file = tmp_path / "report.json"

    fake_result = AgentResult(
        findings=[Finding(title="Test issue", severity="high", description="Desc")],
        notes=["Note"],
    )

    class DummyAgent:
        def __init__(self, profile: str) -> None:
            self.profile = profile

        def run(self, target: str):
            return fake_result

    cli_main_module = importlib.import_module("security.agent_framework.cli.main")
    monkeypatch.setattr(cli_main_module, "SecurityAgent", DummyAgent)

    sent_requests = []
    s3_calls = []
    confluence_calls = []
    ticket_webhook_calls = []

    def fake_post(url, **kwargs):
        sent_requests.append((url, kwargs))

        class _Response:
            def raise_for_status(self) -> None:
                return None

        return _Response()

    monkeypatch.setattr(cli_main_module.httpx, "post", fake_post)

    def fake_upload_to_s3(*args, **kwargs):
        s3_calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(cli_main_module, "upload_to_s3", fake_upload_to_s3)

    def fake_publish_to_confluence(**kwargs):
        confluence_calls.append(kwargs)
        return "https://confluence.test/display/SEC/Report"

    monkeypatch.setattr(cli_main_module, "publish_to_confluence", fake_publish_to_confluence)

    def fake_ticket_webhook(*, webhook_url, tickets):
        ticket_webhook_calls.append((webhook_url, tickets))

    monkeypatch.setattr(cli_main_module, "send_ticket_webhook", fake_ticket_webhook)

    markdown_file = tmp_path / "report.md"
    args = SimpleNamespace(
        profile="web-api",
        targets=["http://example.com"],
        format="json",
        output=str(output_file),
        markdown=str(markdown_file),
        html=str(tmp_path / "report.html"),
        knowledge_base=str(tmp_path / "kb.jsonl"),
        publish_dir=str(tmp_path / "publish"),
        publish_url_base="http://portal.local",
        slack_webhook="https://slack.test/webhook",
        s3_bucket="security-reports",
        s3_prefix="runs",
        s3_region="us-east-1",
        s3_endpoint=None,
        s3_access_key=None,
        s3_secret_key=None,
        confluence_url="https://confluence.test",
        confluence_user="sec-bot",
        confluence_token="token",
        confluence_space="SEC",
        confluence_parent=None,
        tickets_dir=str(tmp_path / "tickets"),
        ticket_prefix="SEC",
        ticket_webhook="https://tickets.test/webhook",
        neo4j_url=None,
        neo4j_user=None,
        neo4j_password=None,
        neo4j_database="neo4j",
        submit=False,
        manager_url=cli_main_module.DEFAULT_MANAGER_URL,
        dry_run=False,
    )
    spec = cli_main_module.RunSpec(
        targets=["http://example.com"],
        instruction=None,
        profile="web-api",
    )
    exit_code = handle_local_run(args, spec, "test-run-id")

    assert exit_code == 2  # high severity -> exit code 2
    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert data["profile"] == "web-api"
    assert data["results"][0]["findings"][0]["title"] == "Test issue"
    markdown = markdown_file.read_text(encoding="utf-8")
    assert "Security Scan Report" in markdown
    assert "Test issue" in markdown
    assert "High" in markdown
    html_content = Path(args.html).read_text(encoding="utf-8")
    assert "<html" in html_content.lower()
    kb_content = Path(args.knowledge_base).read_text(encoding="utf-8")
    assert "Test issue" in kb_content
    publish_dir = Path(args.publish_dir)
    assert (publish_dir / "test-run-id.md").exists()
    assert (publish_dir / "test-run-id.html").exists()
    assert sent_requests and sent_requests[0][0] == args.slack_webhook
    slack_text = sent_requests[0][1]["json"]["text"]
    assert "🚨 High: 1" in slack_text
    assert "<http://portal.local/test-run-id.html|HTML>" in slack_text
    assert "Confluence" in slack_text
    assert any(
        call["kwargs"].get("bucket") == args.s3_bucket or call["args"][0] == args.s3_bucket
        for call in s3_calls
    )
    assert confluence_calls and confluence_calls[0]["space"] == "SEC"
    tickets_path = Path(args.tickets_dir) / "test-run-id.json"
    ticket_data = json.loads(tickets_path.read_text(encoding="utf-8"))
    assert ticket_data[0]["title"].startswith("SEC")
    assert ticket_webhook_calls and ticket_webhook_calls[0][0] == args.ticket_webhook


def test_cli_config_file(monkeypatch, tmp_path):
    cli_main_module = importlib.import_module("security.agent_framework.cli.main")

    fake_result = AgentResult(
        findings=[Finding(title="Config issue", severity="high", description="Desc")],
        notes=["ConfigNote"],
    )

    class DummyAgent:
        def __init__(self, profile: str) -> None:
            self.profile = profile

        def run(self, target: str):
            return fake_result

    monkeypatch.setattr(cli_main_module, "SecurityAgent", DummyAgent)

    output_path = tmp_path / "cfg.json"
    markdown_path = tmp_path / "cfg.md"
    html_path = tmp_path / "cfg.html"

    config_path = tmp_path / "scan.yaml"
    config_path.write_text(
        "\n".join(
            [
                "targets:",
                "  - http://cfg.local",
                "profile: web-api",
                "local: true",
                "format: json",
                f"output: {output_path}",
                f"markdown: {markdown_path}",
                f"html: {html_path}",
            ]
        ),
        encoding="utf-8",
    )

    config_data = cli_main_module.load_config_data(str(config_path))
    assert config_data["local"] is True

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "security-cli",
            "--config",
            str(config_path),
            "run",
        ],
    )

    args = cli_main_module.parse_args()
    assert args.local is True
    exit_code = cli_main_module.handle_run(args)
    assert exit_code == 2
    assert output_path.exists()
    assert markdown_path.exists()
    assert html_path.exists()


def test_preset_copy(tmp_path):
    cli_main_module = importlib.import_module("security.agent_framework.cli.main")
    args = SimpleNamespace(name="web-api", output=str(tmp_path / "custom.yaml"), list=False, show=False)
    exit_code = cli_main_module.handle_preset(args)
    assert exit_code == 0
    assert (tmp_path / "custom.yaml").exists()
