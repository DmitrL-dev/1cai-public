"""Load an owned EDT fixture into a fresh 1C base and verify its round trip."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from rentgen_core.native_platform import CONTEXTS, NativePlatform  # noqa: E402

FIXTURE = ROOT / "packaging/fixtures/edt-metadata-v1"
if not __debug__:
    raise RuntimeError("Verification requires assertions; do not use Python -O")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def local(element):
    return element.tag.rsplit("}", 1)[-1]


def object_named(tree, kind, name):
    matches = [
        node
        for node in tree.iter()
        if local(node) == kind
        and any(local(p) == "Name" and p.text == name for p in node.iter())
    ]
    if len(matches) != 1:
        raise ValueError("Fixture object missing or ambiguous")
    return matches[0]


def verify_structure(source, restored, phase):
    catalog_path = "Catalogs/Products.xml"
    before = ET.parse(FIXTURE / "baseline" / catalog_path).getroot()
    expected = ET.parse(source / catalog_path).getroot()
    actual = ET.parse(restored / catalog_path).getroot()
    identity = object_named(before, "Catalog", "Products").attrib["uuid"]
    for tree in (expected, actual):
        assert object_named(tree, "Catalog", "Products").attrib["uuid"] == identity
    name = "Article" if phase == "created" else "SKU"
    attribute = object_named(actual, "Attribute", name)
    created = ET.parse(FIXTURE / "created" / catalog_path).getroot()
    assert (
        attribute.attrib["uuid"]
        == object_named(created, "Attribute", "Article").attrib["uuid"]
    )
    assert any(local(e) == "Length" and e.text == "32" for e in attribute.iter())
    form_metadata = "Catalogs/Products/Forms/ItemForm.xml"
    form_ids = [
        object_named(
            ET.parse(folder / form_metadata).getroot(), "Form", "ItemForm"
        ).attrib["uuid"]
        for folder in (FIXTURE / "created", source, restored)
    ]
    assert len(set(form_ids)) == 1
    form_path = "Catalogs/Products/Forms/ItemForm/Ext/Form.xml"
    bindings = []
    element_ids = []
    for folder in (source, restored):
        form = ET.parse(folder / form_path).getroot()
        field = next(
            e
            for e in form.iter()
            if local(e) == "InputField" and e.get("name") == "Article"
        )
        binding = next(e.text for e in field if local(e) == "DataPath")
        owner, suffix = binding.split(".")
        main = next(
            e for e in form.iter() if local(e) == "Attribute" and e.get("name") == owner
        )
        assert suffix == name
        assert any(e.text == "cfg:CatalogObject.Products" for e in main.iter())
        bindings.append(binding)
        element_ids.append((field.attrib["id"], main.attrib["id"]))
    assert bindings[0] == bindings[1]
    assert element_ids[0] == element_ids[1]
    return {
        "catalog_uuid": identity,
        "attribute_uuid": attribute.attrib["uuid"],
        "attribute": name,
        "string_length": 32,
        "form_binding": bindings[0],
        "form_uuid": form_ids[0],
        "field_id": element_ids[0][0],
        "main_attribute_id": element_ids[0][1],
    }


def verify(platform, platform_hash, phase, output):
    manifest = json.loads((FIXTURE / "manifest.json").read_text("utf-8"))
    actual = {
        p.relative_to(FIXTURE).as_posix(): digest(p)
        for folder in ("baseline", "created", "renamed")
        for p in (FIXTURE / folder).rglob("*")
        if p.is_file()
    }
    if actual != manifest["files"]:
        raise ValueError("Fixture differs from the accepted experiment")
    native = NativePlatform(platform, platform_hash)

    def authorize():
        if digest(platform) != platform_hash:
            raise ValueError("Platform executable differs from expected SHA256")

    authorize()
    output.mkdir(parents=True, exist_ok=False)
    source = FIXTURE / phase
    base, restored = output / "infobase", output / "restored"
    restored.mkdir()
    common = ["DESIGNER", "/F", base]
    commands = [
        ("create", ["CREATEINFOBASE", f'File="{base}";']),
        ("load", [*common, "/LoadConfigFromFiles", source]),
        ("update", [*common, "/UpdateDBCfg"]),
        ("check", [*common, "/CheckConfig", *CONTEXTS]),
        ("dump", [*common, "/DumpConfigToFiles", restored]),
    ]
    steps, deadline = [], time.monotonic() + 600
    for name, args in commands:
        step = native.invoke(output, name, args, authorize, deadline)
        steps.append(step)
        (output / "steps.json").write_text(
            json.dumps(steps, ensure_ascii=False, indent=2), "utf-8"
        )
        if step["exit_code"] != 0:
            raise ValueError("Native step failed: " + name)
    record = {
        "fixture": "edt-metadata-v1",
        "phase": phase,
        "platform_sha256": platform_hash,
        "native_load_update_check_dump": True,
        "structure": verify_structure(source, restored, phase),
        "business_data_execution": False,
        "product_apply_undo": False,
    }
    (output / "acceptance.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), "utf-8"
    )
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", type=Path, required=True)
    parser.add_argument("--platform-sha256", required=True)
    parser.add_argument("--phase", choices=("created", "renamed"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            verify(
                args.platform.resolve(),
                args.platform_sha256,
                args.phase,
                args.output.resolve(),
            ),
            ensure_ascii=False,
        )
    )
