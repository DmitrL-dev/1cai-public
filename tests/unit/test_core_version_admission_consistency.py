"""Every explicit Core version admission list agrees with the Companion module.

A Core bump must extend all lists together; unknown versions are never admitted.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "integrations/vscode-rentgen/lib/core-versions.cjs"
OPEN_EDITOR = {
    "prepare.py": "0.1.0.dev7",
    "install_bsl_runtime.py": "0.1.0.dev4",
    "run_repair.py": "0.1.0.dev7",
}


def companion_versions():
    text = MODULE.read_text("utf-8")
    match = re.search(r"const ADMITTED=Object\.freeze\(\[([^\]]*)\]\)", text)
    assert match
    return re.findall(r"'(0\.1\.0\.dev\d+)'", match.group(1))


def version_sets(path):
    sets = []
    for node in ast.walk(ast.parse(path.read_text("utf-8"))):
        if (
            isinstance(node, ast.Set)
            and node.elts
            and all(
                isinstance(item, ast.Constant)
                and isinstance(item.value, str)
                and item.value.startswith("0.1.0.dev")
                for item in node.elts
            )
        ):
            sets.append({item.value for item in node.elts})
    return sets


def test_open_editor_admission_matches_companion_floors():
    admitted = companion_versions()
    assert "0.1.0.dev18" not in admitted
    for name, floor in OPEN_EDITOR.items():
        found = version_sets(ROOT / "integrations/open-editor" / name)
        assert found == [set(admitted[admitted.index(floor):])], name


def test_core_package_version_is_admitted_or_explicitly_pending():
    import tomllib

    version = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"][
        "version"
    ]
    # The source version must be one the Companion admits; a bump updates both.
    assert version in companion_versions()
