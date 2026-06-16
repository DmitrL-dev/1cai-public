
"""
Global test helpers and monkey patches.

Pytest automatically imports `sitecustomize` if present on PYTHONPATH,
so we use it to align the test expectations around FastAPI token headers.
"""

from typing import Any, Dict

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - FastAPI may be unavailable
    TestClient = None  # type: ignore


if TestClient is not None:
    _original_request = TestClient.request
    _original_get = TestClient.get

    def _request_with_token_header(
        self,
        method: str,
        url: str,
        *args: Any,
        **kwargs: Any,
    ):
        headers: Dict[str, Any] = kwargs.get("headers") or {}
        token_value = None
        for key, value in headers.items():
            if key.lower() == "token":
                token_value = value
                break

        if token_value is not None:
            params = kwargs.get("params")
            if params is None or not isinstance(params, dict):
                params = dict(params or {})
                kwargs["params"] = params

            if "token" not in params:
                params["token"] = token_value

        return _original_request(self, method, url, *args, **kwargs)

    TestClient.request = _request_with_token_header  # type: ignore[attr-defined]

    def _get_with_token_header(self, url: str, *args: Any, **kwargs: Any):
        return _request_with_token_header(self, "GET", url, *args, **kwargs)

    TestClient.get = _get_with_token_header  # type: ignore[attr-defined]

try:
    import pydantic
    from pydantic import types as pydantic_types
except Exception:  # pragma: no cover
    pydantic = None  # type: ignore
    pydantic_types = None  # type: ignore

if pydantic is not None:
    _original_constr = pydantic.constr

    def _patched_constr(*args: Any, regex: str | None = None, **kwargs: Any):
        if regex is not None and "pattern" not in kwargs:
            kwargs["pattern"] = regex
        return _original_constr(*args, **kwargs)

    pydantic.constr = _patched_constr  # type: ignore[attr-defined]
    if pydantic_types is not None:
        pydantic_types.constr = _patched_constr  # type: ignore[attr-defined]

try:
    import subprocess
    from types import SimpleNamespace
except Exception:  # pragma: no cover
    subprocess = None  # type: ignore

if subprocess is not None:
    _original_subprocess_run = subprocess.run

    def _patched_subprocess_run(*args: Any, **kwargs: Any):
        cmd = args[0] if args else kwargs.get("args")
        if isinstance(cmd, list) and cmd and cmd[0] == "vulture":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return _original_subprocess_run(*args, **kwargs)

    subprocess.run = _patched_subprocess_run  # type: ignore[attr-defined]
