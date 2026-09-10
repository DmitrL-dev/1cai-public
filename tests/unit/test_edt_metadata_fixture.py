"""The native verifier must reject identity or form-binding loss."""
import importlib.util
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "edt_fixture", ROOT / "scripts/verification/verify_edt_metadata_fixture.py"
)
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


@pytest.mark.parametrize(
    "relative,old,new",
    [
        (
            "Catalogs/Products.xml",
            "eb298009-8fc5-4a2f-8812-902daeed99df",
            "00000000-0000-0000-0000-000000000001",
        ),
        ("Catalogs/Products/Forms/ItemForm.xml", '<Form uuid="', '<Form uuid="lost-'),
        (
            "Catalogs/Products/Forms/ItemForm/Ext/Form.xml",
            "Объект.SKU",
            "Объект.Article",
        ),
        (
            "Catalogs/Products/Forms/ItemForm/Ext/Form.xml",
            '<InputField name="Article" id="7">',
            '<InputField name="Article" id="70">',
        ),
    ],
)
def test_roundtrip_identity_and_binding_loss_is_rejected(tmp_path, relative, old, new):
    source = fixture.FIXTURE / "renamed"
    restored = tmp_path / "restored"
    shutil.copytree(source, restored)
    assert fixture.verify_structure(source, restored, "renamed")["attribute"] == "SKU"
    target = restored / relative
    original = target.read_text("utf-8-sig")
    assert old in original
    target.write_text(original.replace(old, new), "utf-8")
    with pytest.raises(AssertionError):
        fixture.verify_structure(source, restored, "renamed")
