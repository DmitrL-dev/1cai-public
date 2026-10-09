"""Startup refusals only; these checks do not run a native observer."""

import builtins
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from rentgen_core import observer_cli
from rentgen_core.errors import CoreError


PROJECT = "11111111-1111-4111-8111-111111111111"


def arguments(root):
    return [
        "status", "--registry", str(root / "registry.sqlite3"),
        "--project", PROJECT, "--profile", str(root / "profile.json"),
    ]


class ObserverCliStartupTests(unittest.TestCase):
    def invoke(self, argv):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = observer_cli.main(argv)
        self.assertEqual(errors.getvalue(), "")
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        return code, json.loads(output.getvalue())

    def test_identity_refusal_precedes_optional_graph_import(self):
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name.startswith("rentgen_graph"):
                self.fail("Optional graph import preceded identity refusal")
            return original_import(name, *args, **kwargs)

        error = CoreError("LOCAL_IDENTITY_UNAVAILABLE", "Identity unavailable")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "missing"
            with patch.object(observer_cli, "current_windows_principal", side_effect=error), \
                 patch.object(observer_cli, "LocalRuntime", side_effect=AssertionError("Runtime constructed")), \
                 patch("builtins.__import__", side_effect=guarded_import):
                code, value = self.invoke(arguments(root))
            self.assertEqual(code, 2)
            self.assertEqual(value, {"error": {"code": error.code, "message": str(error)}})
            self.assertFalse(root.exists())

    def test_missing_graph_adapter_returns_structured_error(self):
        original_import = builtins.__import__
        imports = []

        def missing_graph(name, *args, **kwargs):
            if name.startswith("rentgen_graph"):
                imports.append(name)
                raise ModuleNotFoundError("private dependency location")
            return original_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "missing"
            with patch.object(observer_cli, "current_windows_principal", return_value=object()) as identity, \
                 patch.object(observer_cli, "LocalRuntime", side_effect=AssertionError("Runtime constructed")), \
                 patch("builtins.__import__", side_effect=missing_graph):
                code, value = self.invoke(arguments(root))
            identity.assert_called_once_with()
            self.assertEqual(imports, ["rentgen_graph.snapshot_adapter"])
            self.assertEqual(code, 2)
            self.assertEqual(value, {"error": {
                "code": "GRAPH_ADAPTER_UNAVAILABLE",
                "message": "Install the supported rentgen_graph package",
            }})
            self.assertFalse(root.exists())

    def test_argument_error_precedes_identity_and_graph_setup(self):
        with patch.object(observer_cli, "current_windows_principal", side_effect=AssertionError("Identity queried")), \
             patch.object(observer_cli, "LocalRuntime", side_effect=AssertionError("Runtime constructed")):
            code, value = self.invoke(arguments(Path("missing")) + ["--interval", "0"])
        self.assertEqual(code, 2)
        self.assertEqual(value["error"]["code"], "INVALID_ARGUMENT")

    @unittest.skipUnless(sys.platform == "linux", "Actual Linux startup refusal")
    def test_actual_linux_identity_refuses_before_optional_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "missing"
            code, value = self.invoke(arguments(root))
            self.assertEqual(code, 2)
            self.assertEqual(value, {"error": {
                "code": "LOCAL_IDENTITY_UNAVAILABLE",
                "message": "Local process identity requires Windows",
            }})
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
