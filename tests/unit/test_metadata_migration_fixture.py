import importlib.util
import os
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from rentgen_core.edt_inventory import exported_inventory

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows retained inputs")


@pytest.fixture
def verifier(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts/verification"))
    spec = importlib.util.spec_from_file_location(
        "migration_fixture", ROOT / "scripts/verification/verify_metadata_migration.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_engine_adaptation_preserves_borrowed_identity_and_unrelated_code(
    verifier, tmp_path
):
    source = tmp_path / "engine"
    (source / "Languages").mkdir(parents=True)
    raw = (
        ROOT / "packaging/fixtures/edt-metadata-v1/created/Languages/Russian.xml"
    ).read_bytes()
    language = raw.replace(
        b"<Name>Russian</Name>", "<Name>Русский</Name>".encode()
    ).replace(
        b"<Properties>", b"<Properties><ObjectBelonging>Adopted</ObjectBelonging>"
    )
    (source / "Languages/Русский.xml").write_bytes(language)
    (source / "Configuration.xml").write_text(
        "<ChildObjects><Language>Русский</Language></ChildObjects>", "utf-8"
    )
    (source / "ConfigDumpInfo.xml").write_text(
        '<Metadata name="Language.Русский" id="unchanged"/>', "utf-8"
    )
    (source / "unrelated.bsl").write_bytes(b"unchanged test-engine module")
    rows = exported_inventory(source, authorize=lambda: None)
    target = tmp_path / "prepared"
    verifier.prepare_engine_language(source, target, rows)
    namespace = "{http://v8.1c.ru/8.3/MDClasses}"
    original = ET.parse(source / "Languages/Русский.xml").find(namespace + "Language")
    prepared = ET.parse(target / "Languages/Russian.xml").find(namespace + "Language")
    assert prepared.attrib["uuid"] == original.attrib["uuid"]
    assert (
        prepared.find(namespace + "Properties/" + namespace + "LanguageCode").text
        == "ru"
    )
    assert (
        prepared.find(namespace + "Properties/" + namespace + "ObjectBelonging").text
        == "Adopted"
    )
    assert not (target / "Languages/Русский.xml").exists()
    assert (target / "unrelated.bsl").read_bytes() == (
        source / "unrelated.bsl"
    ).read_bytes()
    assert 'name="Language.Russian" id="unchanged"' in (
        target / "ConfigDumpInfo.xml"
    ).read_text("utf-8")
    assert exported_inventory(source, authorize=lambda: None) == rows


def test_optimized_python_cannot_skip_structural_assertions():
    script = "import sys;sys.path.insert(0,'scripts/verification');import verify_metadata_migration as v;v.verify(None)"
    result = subprocess.run(
        [sys.executable, "-O", "-c", script], cwd=ROOT, capture_output=True, timeout=10
    )
    assert result.returncode != 0
    assert b"do not use Python -O" in result.stderr


def test_output_cannot_modify_retained_input_tree(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts/verification"))
    import verify_metadata_migration as verifier

    source_run = tmp_path / "run"
    source_run.mkdir()
    output = source_run / "input/results"
    with pytest.raises(ValueError, match="outside retained input"):
        verifier.verify(SimpleNamespace(input_run=source_run, output=output))
    assert not output.exists()
