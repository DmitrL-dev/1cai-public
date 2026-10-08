"""Portable CLI parsing and real Linux refusal; no Windows IO is substituted."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from rentgen_core import capabilities, cli
from rentgen_core.errors import CoreError


PROJECT = "11111111-1111-4111-8111-111111111111"
DRAFT = "22222222-2222-4222-8222-222222222222"
OPERATION = "33333333-3333-4333-8333-333333333333"
SNAPSHOT = "a" * 64


def arguments(command, root=Path("missing")):
    common = [command, "--registry", str(root / "registry.sqlite3"),
              "--project", PROJECT, "--snapshot", SNAPSHOT,
              "--draft-id", DRAFT, "--operation-id", OPERATION]
    return common + (
        ["--source-ref-json", str(root / "source-ref.json"), "--title=--help"]
        if command == "draft-start" else
        ["--edits-json", str(root / "edits.json"), "--expected-revision", "1"]
    )


class DraftCliContractTests(unittest.TestCase):
    def test_explicit_binding_and_option_like_title_are_preserved(self):
        start = cli._parser().parse_args(arguments("draft-start"))
        self.assertEqual(start.title, "--help")
        self.assertEqual(start.source_ref_json, Path("missing/source-ref.json"))
        self.assertFalse(hasattr(start, "expected_revision"))
        edit = cli._parser().parse_args(arguments("draft-edit"))
        self.assertEqual(edit.edits_json, Path("missing/edits.json"))
        self.assertEqual(edit.expected_revision, 1)
        for selected in (start, edit):
            self.assertEqual((selected.project, selected.snapshot, selected.draft_id,
                              selected.operation_id), (PROJECT, SNAPSHOT, DRAFT, OPERATION))

    def test_missing_and_repeated_mutation_arguments_are_rejected(self):
        for command in ("draft-start", "draft-edit"):
            required = ["--snapshot", "--draft-id", "--operation-id"]
            required += (["--source-ref-json"] if command == "draft-start"
                         else ["--edits-json", "--expected-revision"])
            for option in required:
                with self.subTest(command=command, option=option, kind="missing"):
                    values = arguments(command)
                    index = values.index(option)
                    del values[index:index + 2]
                    with self.assertRaises(CoreError) as caught:
                        cli._parser().parse_args(values)
                    self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")
                with self.subTest(command=command, option=option, kind="repeated"):
                    values = arguments(command)
                    values += [option, values[values.index(option) + 1]]
                    with self.assertRaises(CoreError) as caught:
                        cli._parser().parse_args(values)
                    self.assertIn("Repeated option", str(caught.exception))
        with self.assertRaises(CoreError):
            cli._parser().parse_args(arguments("draft-start") + ["--expected-revision", "1"])
        with self.assertRaises(CoreError):
            cli._parser().parse_args(arguments("draft-start")[:-1])

    def test_unsupported_os_refuses_before_identity_or_runtime(self):
        for platform in ("darwin", "freebsd"):
            for command in ("draft-start", "draft-edit"):
                with self.subTest(platform=platform, command=command), \
                     patch.object(capabilities, "_platform", platform), \
                     patch.object(cli, "current_local_principal", side_effect=AssertionError("identity read")), \
                     patch.object(cli, "_runtime", side_effect=AssertionError("runtime opened")):
                    with self.assertRaises(CoreError) as caught:
                        cli._execute(cli._parser().parse_args(arguments(command)))
                    self.assertEqual(caught.exception.code, "CAPABILITY_UNAVAILABLE")

    @unittest.skipUnless(sys.platform == "linux", "Actual Linux process refusal")
    def test_real_linux_process_refuses_before_opening_any_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "uncreated"
            for command in ("draft-start", "draft-edit"):
                with self.subTest(command=command):
                    result = subprocess.run(
                        [sys.executable, "-S", "-m", "rentgen_core", *arguments(command, root)],
                        cwd=Path(__file__).resolve().parents[2],
                        capture_output=True, timeout=5, check=False,
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stderr, b"")
                    self.assertEqual(len(result.stdout.splitlines()), 1)
                    value = json.loads(result.stdout)
                    self.assertEqual(value["error"]["code"], "CAPABILITY_UNAVAILABLE")
                    self.assertEqual(value["error"]["details"]["operation"], command)
                    self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
