"""Model output is only a bounded code edit, never an executable tool call."""
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading

import anyio

import pytest


@pytest.fixture
def model():
    spec = importlib.util.spec_from_file_location(
        "repair_model",
        Path(__file__).resolve().parents[2]
        / "integrations/open-editor/repair_model.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_edits_preserve_original_encoding_and_use_exact_matches(model):
    raw = (
        b"\xef\xbb\xbf"
        + "Процедура Проверка()\r\n    Старый();\r\nКонецПроцедуры\r\n".encode()
    )
    response = json.dumps(
        {
            "edits": [{"old_text": "    Старый();\n", "new_text": "    Новый();\n"}],
            "summary": "Замена вызова",
        }
    )
    parsed = model.parse_edit_response(response, raw)
    assert parsed["edits"][0]["old_text"].endswith("\r\n")
    assert parsed["candidate"] == raw.replace("Старый".encode(), "Новый".encode())


@pytest.mark.parametrize(
    "response",
    [
        '{"edits":[],"summary":"x"}',
        '{"edits":[],"edits":[],"summary":"x"}',
        '{"edits":[{"old_text":"Old","new_text":"New"}],"summary":"x","tool":"shell"}',
        '{"edits":[{"old_text":"Old","new_text":"Old"}],"summary":"x"}',
        '{"edits":[{"old_text":"absent","new_text":"New"}],"summary":"x"}',
        '{"edits":[{"old_text":"Old","new_text":"New","operation_id":"x"}],"summary":"x"}',
        "```json\n{}\n```",
    ],
)
def test_invalid_model_response_cannot_become_an_edit(model, response):
    with pytest.raises(ValueError):
        model.parse_edit_response(response, b"Old\n")


def test_malformed_json_has_a_stable_error_without_reflecting_model_text(model):
    with pytest.raises(ValueError, match="^MODEL_INVALID_JSON$"):
        model.parse_edit_response('{"edits": [secret-invalid-value]}', b"Old\n")


def test_one_complete_json_fence_is_a_supported_envelope(model):
    payload = json.dumps(
        {"edits": [{"old_text": "Old", "new_text": "New"}], "summary": "Change"}
    )
    assert (
        model.parse_edit_response("```json\n" + payload + "\n```", b"Old\n")[
            "candidate"
        ]
        == b"New\n"
    )
    for envelope in [
        "Explanation\n```json\n" + payload + "\n```",
        "```json\n" + payload + "\n```\nExtra",
        "```json\n" + payload + "\n```\n```json\n{}\n```",
    ]:
        with pytest.raises(ValueError):
            model.parse_edit_response(envelope, b"Old\n")


def test_ambiguous_overlap_and_utf8_limits_are_rejected(model):
    for raw, edits in [
        (b"Old Old", [{"old_text": "Old", "new_text": "New"}]),
        (
            b"Old",
            [
                {"old_text": "Old", "new_text": "New"},
                {"old_text": "ld", "new_text": "x"},
            ],
        ),
        (b"Old", [{"old_text": "Old", "new_text": "я" * 4097}]),
    ]:
        with pytest.raises(ValueError):
            model.parse_edit_response(json.dumps({"edits": edits, "summary": "x"}), raw)


def test_endpoint_requires_literal_loopback_without_credentials_or_paths(model):
    for url in [
        "https://example.com",
        "http://localhost:11434",
        "http://user:pass@127.0.0.1:11434",
        "http://127.0.0.1:11434/v1",
    ]:
        with pytest.raises(ValueError):
            model.OllamaEditor("qwen3.5:4b", endpoint=url)


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "fenced",
        "malformed",
        "thinking",
        "redirect",
        "incomplete",
        "truncated",
        "tools",
        "oversize",
    ],
)
def test_actual_http_request_has_schema_and_no_retry_or_tools(model, case):
    requests, captured = [], []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(request)
            self.send_response(302 if case == "redirect" else 200)
            if case == "redirect":
                self.send_header("Location", "/unexpected")
            self.end_headers()
            response = {
                "model": "qwen3.5:4b",
                "done": case != "incomplete",
                "done_reason": "length" if case == "truncated" else "stop",
                "eval_count": 4096 if case == "truncated" else 30,
                "message": {
                    "role": "assistant",
                    "thinking": "PRIVATE_REASONING_MUST_NOT_BE_CAPTURED",
                    "content": json.dumps(
                        {
                            "edits": [{"old_text": "Old", "new_text": "New"}],
                            "summary": "Changed",
                        }
                    ),
                },
            }
            if case == "fenced":
                response["message"]["content"] = (
                    "```json\n" + response["message"]["content"] + "\n```"
                )
            if case == "malformed":
                response["message"]["content"] = "invalid JSON"
            if case == "tools":
                response["message"]["tool_calls"] = [{"function": {"name": "shell"}}]
            self.wfile.write(
                b"x" * 131073 if case == "oversize" else json.dumps(response).encode()
            )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        editor = model.OllamaEditor(
            "qwen3.5:4b",
            endpoint=f"http://127.0.0.1:{server.server_port}",
            thinking=case == "thinking",
            on_content=captured.append,
        )
        if case in {"valid", "thinking", "fenced"}:
            result = anyio.run(
                editor.propose, b"\xef\xbb\xbfOld\r\n", "Change call", []
            )
            assert result["candidate"] == b"\xef\xbb\xbfNew\r\n"
        else:
            with pytest.raises(ValueError):
                anyio.run(editor.propose, b"Old\n", "Change call", [])
        assert len(requests) == 1
        if case in {"valid", "thinking", "fenced", "malformed"}:
            assert len(captured) == 1 and "PRIVATE_REASONING" not in captured[0]
        else:
            assert captured == []
        request = requests[0]
        assert request["format"] == model.EDIT_SCHEMA and request["stream"] is False
        assert request["keep_alive"] == 0 and "tools" not in request
        assert request["think"] == (case == "thinking")
        if case == "truncated":
            assert editor.last_metrics["done_reason"] == "length"
            assert editor.last_metrics["eval_count"] == 4096
            assert set(editor.last_metrics).isdisjoint(
                {"content", "thinking_text", "source"}
            )
        user = json.loads(request["messages"][1]["content"])
        assert user["source"] == "Old\n" and set(user) == {
            "source",
            "instruction",
            "diagnostics",
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
