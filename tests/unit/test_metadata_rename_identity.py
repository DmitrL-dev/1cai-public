"""IDE-SC-08: a rename candidate may change exactly one UUID-owned name.

Synthetic Designer XML from the owned EDT fixture plus an unrelated catalog with
a same-name attribute. Only retained-file pinning is replaced by a plain reader;
the Windows end-to-end preview is covered in test_metadata_preview.py.
"""
from pathlib import Path
import re
import shutil
from uuid import NAMESPACE_URL, uuid5

import pytest

from rentgen_core import metadata_preview as preview
from rentgen_core.errors import CoreError

FIXTURE = Path(__file__).resolve().parents[2] / "packaging/fixtures/edt-metadata-v1"
CATALOG_UUID = "fb28b18e-d2a3-4f48-8390-c0d609c9e7c0"
ATTRIBUTE_UUID = "eb298009-8fc5-4a2f-8812-902daeed99df"
_UUID = re.compile(rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
UNRELATED_PATH = "Catalogs/Customers.xml"
UNRELATED_MODULE = "Catalogs/Customers/Ext/ObjectModule.bsl"


def unrelated_uuid(value):
    return str(uuid5(NAMESPACE_URL, "rentgen-test:" + value))


def unrelated_catalog():
    """Customers with its own UUIDs and an attribute also named Article."""
    raw = (FIXTURE / "created/Catalogs/Products.xml").read_bytes()
    raw = raw.replace(
        b"<DefaultObjectForm>Catalog.Products.Form.ItemForm</DefaultObjectForm>",
        b"<DefaultObjectForm/>",
    ).replace(b"\t\t\t<Form>ItemForm</Form>\r\n", b"")
    raw = raw.replace(b"Products", b"Customers")
    raw = _UUID.sub(lambda match: unrelated_uuid(match.group().decode()).encode(), raw)
    assert raw.count(b"<Name>Article</Name>") == 1
    return raw


UNRELATED_FILES = {
    UNRELATED_PATH: unrelated_catalog(),
    UNRELATED_MODULE: (
        "Процедура ПередЗаписью(Отказ)\r\n"
        "\tЗначение = Article;\r\n"
        "КонецПроцедуры\r\n"
    ).encode(),
}
REQUEST = {
    "catalog": {"name": "Products", "uuid": CATALOG_UUID},
    "attribute": {"name": "Article", "uuid": ATTRIBUTE_UUID},
    "new_name": "SKU",
}


def export(tmp_path, phase, **changes):
    root = tmp_path / phase
    shutil.copytree(FIXTURE / phase, root)
    for path, raw in [*UNRELATED_FILES.items(), *changes.items()]:
        target = root / path
        if raw is None:
            target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    rows = [
        {"path": path.relative_to(root).as_posix()}
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]
    return root, rows


def identities(monkeypatch, tmp_path, phase, request, **changes):
    monkeypatch.setattr(
        preview, "read_retained", lambda path, maximum: Path(path).read_bytes()
    )
    root, rows = export(tmp_path, phase, **changes)
    return preview._verify_identity(root, rows, request, lambda: None)


def renamed_request():
    return {
        **REQUEST,
        "attribute": {"name": "SKU", "uuid": ATTRIBUTE_UUID},
        "new_name": "Article",
    }


def test_rename_changes_only_the_owned_attribute_name(monkeypatch, tmp_path):
    before = identities(monkeypatch, tmp_path, "created", REQUEST)
    after = identities(monkeypatch, tmp_path, "renamed", renamed_request())
    preview._require_only_renamed(before, after, REQUEST)
    unrelated = (unrelated_uuid(ATTRIBUTE_UUID), "Article")
    assert before[unrelated] == after[unrelated] == 1
    assert before[ATTRIBUTE_UUID, "Article"] == after[ATTRIBUTE_UUID, "SKU"] == 1
    assert after[ATTRIBUTE_UUID, "Article"] == 0
    assert before[CATALOG_UUID, "Products"] == after[CATALOG_UUID, "Products"] == 1
    assert (tmp_path / "created" / UNRELATED_PATH).read_bytes() == (
        tmp_path / "renamed" / UNRELATED_PATH
    ).read_bytes()


def _same_name_renamed():
    return UNRELATED_FILES[UNRELATED_PATH].replace(
        b"<Name>Article</Name>", b"<Name>SKU</Name>"
    )


def _uuid_replaced():
    old = unrelated_uuid(ATTRIBUTE_UUID).encode()
    new = unrelated_uuid("replaced").encode()
    return UNRELATED_FILES[UNRELATED_PATH].replace(old, new)


@pytest.mark.parametrize(
    "changes",
    [
        {UNRELATED_PATH: _same_name_renamed()},
        {UNRELATED_PATH: _uuid_replaced()},
        {UNRELATED_PATH: None},
        {"Catalogs/Products/Forms/ItemForm.xml": None},
        {
            "Languages/Russian.xml": (FIXTURE / "renamed/Languages/Russian.xml")
            .read_bytes()
            .replace(b"<Name>Russian</Name>", b"<Name>Article</Name>")
        },
    ],
    ids=[
        "same_name_unrelated_renamed",
        "unrelated_uuid_replaced",
        "unrelated_object_removed",
        "owned_form_removed",
        "other_object_renamed",
    ],
)
def test_candidate_cannot_touch_other_identities(monkeypatch, tmp_path, changes):
    before = identities(monkeypatch, tmp_path, "created", REQUEST)
    after = identities(monkeypatch, tmp_path, "renamed", renamed_request(), **changes)
    with pytest.raises(CoreError) as error:
        preview._require_only_renamed(before, after, REQUEST)
    assert error.value.code == "METADATA_PLAN_INVALID"


def test_target_uuid_must_survive_the_rename(monkeypatch, tmp_path):
    raw = (FIXTURE / "renamed/Catalogs/Products.xml").read_bytes()
    replaced = raw.replace(ATTRIBUTE_UUID.encode(), unrelated_uuid("y").encode())
    with pytest.raises(CoreError):
        identities(
            monkeypatch,
            tmp_path,
            "renamed",
            renamed_request(),
            **{"Catalogs/Products.xml": replaced},
        )
