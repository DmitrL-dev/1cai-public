"""Actual EDT MetaDataObject XML identity inventory contract."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from rentgen_core import edt_inventory
from rentgen_core.edt_identity_three_way import plan_edt_identity_three_way
from rentgen_core.context import SnapshotRef
from rentgen_core.errors import CoreError
from rentgen_core.source_configuration import SourceLayerSpec
from rentgen_core.sources import SourceRef


SNAPSHOT = SnapshotRef("12345678-1234-4234-8234-123456789abc", "a" * 64, "a" * 64)
LAYER = SourceLayerSpec("base", 0, "base", ".", "edt")
FIXTURE = (
    Path(__file__).resolve().parents[2] / "packaging/fixtures/edt-metadata-v1/created"
)
CATALOG_UUID = "fb28b18e-d2a3-4f48-8390-c0d609c9e7c0"
ATTRIBUTE_UUID = "eb298009-8fc5-4a2f-8812-902daeed99df"
FORM_UUID = "44821c5c-7eaf-4b40-ba04-dc79e0c71268"


@dataclass
class _Entry:
    ref: SourceRef
    raw: bytes

    @property
    def size_bytes(self):
        return len(self.raw)


class _Capability:
    validation_summary = {"status": "verified"}
    revoked = False

    def __init__(self, entries):
        self._entries = tuple(entries)

    def checkpoint(self):
        if self.revoked:
            raise CoreError("FORBIDDEN", "Revoked")

    @contextmanager
    def transaction(self, principal):
        self.checkpoint()
        yield self

    def require_all(self, permissions):
        assert permissions == {"project:read"}
        self.checkpoint()

    def get_snapshot_layers(self, snapshot_id):
        assert snapshot_id == SNAPSHOT.snapshot_id
        return (LAYER,)

    @contextmanager
    def read_session(self, *, limits):
        self.checkpoint()
        yield self

    def entries(self):
        return self._entries

    def read_source(self, ref):
        self.checkpoint()
        return next(entry.raw for entry in self._entries if entry.ref == ref)


def _context(files):
    entries = []
    for path, raw in files:
        entries.append(
            _Entry(
                SourceRef(SNAPSHOT, "base", path, sha256(raw).hexdigest()),
                raw,
            )
        )
    capability = _Capability(entries)
    return SimpleNamespace(
        snapshot=SNAPSHOT,
        principal="test",
        state=capability,
        sources=capability,
    )


def _fixture(*paths):
    return [(path, (FIXTURE / path).read_bytes()) for path in paths]


def test_actual_metadata_objects_and_path_owned_form_are_inventoried():
    context = _context(
        _fixture(
            "Configuration.xml",
            "Catalogs/Products.xml",
            "Catalogs/Products/Forms/ItemForm.xml",
            "Catalogs/Products/Forms/ItemForm/Ext/Form.xml",
        )
    )
    result = edt_inventory.edt_metadata_inventory(context)

    assert result["parser"] == "edt_identity_v2"
    assert result["owner_basis"] == "direct_xml_containment_and_verified_path_owner"
    assert result["layers"][0]["parsed_mdo_files"] == 3
    assert result["layers"][0]["unparsed_files"] == 1
    assert {
        (row["type"], row["name"], row["canonical_uuid"]) for row in result["objects"]
    } == {
        ("Configuration", "RentgenMD", "c5bbdafc-ac33-454e-98bb-5492e6f90b3d"),
        ("Catalog", "Products", CATALOG_UUID),
        ("Attribute", "Article", ATTRIBUTE_UUID),
        ("Form", "ItemForm", FORM_UUID),
    }
    form = next(row for row in result["objects"] if row["type"] == "Form")
    assert form["owner"]["canonical_uuid"] == CATALOG_UUID
    assert form["owner"]["xml_path"] == "/Catalog"
    assert form["xml_path"] == "/Form"
    assert {ref["relative_path"] for ref in result["source_refs"]} == {
        "Configuration.xml",
        "Catalogs/Products.xml",
        "Catalogs/Products/Forms/ItemForm.xml",
    }


def test_separate_form_requires_a_verified_parent_object():
    with pytest.raises(CoreError) as error:
        edt_inventory.edt_metadata_inventory(
            _context(
                _fixture("Configuration.xml", "Catalogs/Products/Forms/ItemForm.xml")
            )
        )
    assert error.value.code == "EDT_INVENTORY_UNSUPPORTED"
    assert error.value.details["source_ref"]["relative_path"].endswith("ItemForm.xml")


def test_mdo_and_metadat_object_xml_cannot_be_mixed_in_one_layer():
    mdo = (
        b'<md:Configuration xmlns:md="http://g5.1c.ru/v8/dt/metadata/mdclass" '
        b'uuid="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"><name>Demo</name></md:Configuration>'
    )
    with pytest.raises(CoreError) as error:
        edt_inventory.edt_metadata_inventory(
            _context(
                [
                    ("Configuration/Configuration.mdo", mdo),
                    *_fixture("Configuration.xml"),
                ]
            )
        )
    assert error.value.code == "EDT_INVENTORY_UNSUPPORTED"


def test_metadat_object_name_must_match_its_descriptor_path():
    raw = (FIXTURE / "Catalogs/Products.xml").read_bytes()
    with pytest.raises(CoreError) as error:
        edt_inventory.edt_metadata_inventory(_context([("Catalogs/Wrong.xml", raw)]))
    assert error.value.code == "EDT_IDENTITY_INVALID"


def test_foreign_metadat_object_namespace_fails_closed():
    raw = (
        (FIXTURE / "Catalogs/Products.xml")
        .read_bytes()
        .replace(b'xmlns="http://v8.1c.ru/8.3/MDClasses"', b'xmlns="urn:foreign"', 1)
    )
    with pytest.raises(CoreError) as error:
        edt_inventory.edt_metadata_inventory(_context([("Catalogs/Products.xml", raw)]))
    assert error.value.code == "EDT_INVENTORY_UNSUPPORTED"


def test_unknown_uuid_child_is_never_treated_as_opaque():
    raw = (
        (FIXTURE / "Catalogs/Products.xml")
        .read_bytes()
        .replace(
            b"\r\n\t\t</ChildObjects>",
            b'\r\n\t\t\t<Mystery uuid="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"><Properties><Name>Hidden</Name></Properties></Mystery>\r\n\t\t</ChildObjects>',
            1,
        )
    )
    with pytest.raises(CoreError) as error:
        edt_inventory.edt_metadata_inventory(_context([("Catalogs/Products.xml", raw)]))
    assert error.value.code == "EDT_INVENTORY_UNSUPPORTED"


def test_uuid_inside_structural_metadata_is_rejected():
    raw = (
        (FIXTURE / "Catalogs/Products.xml")
        .read_bytes()
        .replace(
            b"<xr:GeneratedType name=",
            b'<xr:GeneratedType uuid="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" name=',
            1,
        )
    )
    with pytest.raises(CoreError) as error:
        edt_inventory.edt_metadata_inventory(_context([("Catalogs/Products.xml", raw)]))
    assert error.value.code == "EDT_INVENTORY_UNSUPPORTED"


def test_uuid_inside_identity_properties_is_rejected():
    raw = (
        (FIXTURE / "Catalogs/Products.xml")
        .read_bytes()
        .replace(
            b"<Name>Products</Name>",
            b'<Name uuid="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa">Products</Name>',
            1,
        )
    )
    with pytest.raises(CoreError) as error:
        edt_inventory.edt_metadata_inventory(_context([("Catalogs/Products.xml", raw)]))
    assert error.value.code == "EDT_INVENTORY_UNSUPPORTED"


def test_uuid_on_metadata_wrapper_is_rejected():
    raw = (
        (FIXTURE / "Catalogs/Products.xml")
        .read_bytes()
        .replace(
            b"<MetaDataObject xmlns=",
            b'<MetaDataObject uuid="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" xmlns=',
            1,
        )
    )
    with pytest.raises(CoreError) as error:
        edt_inventory.edt_metadata_inventory(_context([("Catalogs/Products.xml", raw)]))
    assert error.value.code == "EDT_INVENTORY_UNSUPPORTED"


def test_identity_three_way_accepts_actual_edt_xml_inventory():
    inventory = edt_inventory.edt_metadata_inventory(
        _context(
            _fixture(
                "Configuration.xml",
                "Catalogs/Products.xml",
                "Catalogs/Products/Forms/ItemForm.xml",
            )
        )
    )
    inventory["validation_summary"] = {
        "generation": {
            **inventory["snapshot"],
            "verified_source_files": 3,
            "verified_derived_files": 0,
            "verified_source_bytes": 1,
            "verified_total_bytes": 1,
            "source_digest": "b" * 64,
            "graph_hash": "c" * 64,
            "all_expected_files_verified": True,
            "inventory_checks": "entry_exit",
            "expected_bytes_protected": "retained_handles",
            "temporal_namespace_atomicity": "not_proven",
        }
    }

    result = plan_edt_identity_three_way(inventory, inventory, inventory)

    assert result["scope"] == "edt-identity-v1"
    assert result["counts"]["unchanged"] == len(inventory["objects"])
    assert result["counts"]["unsupported"] == 0


def test_identity_three_way_rejects_colliding_actual_xml_child_positions():
    inventory = edt_inventory.edt_metadata_inventory(
        _context(_fixture("Configuration.xml", "Catalogs/Products.xml"))
    )
    inventory["validation_summary"] = {
        "generation": {
            **inventory["snapshot"],
            "verified_source_files": 2,
            "verified_derived_files": 0,
            "verified_source_bytes": 1,
            "verified_total_bytes": 1,
            "source_digest": "b" * 64,
            "graph_hash": "c" * 64,
            "all_expected_files_verified": True,
            "inventory_checks": "entry_exit",
            "expected_bytes_protected": "retained_handles",
            "temporal_namespace_atomicity": "not_proven",
        }
    }
    child = deepcopy(
        next(row for row in inventory["objects"] if row["type"] == "Attribute")
    )
    child["canonical_uuid"] = child[
        "observed_uuid"
    ] = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
    child["type"] = "Form"
    child["name"] = "OtherForm"
    child["xml_path"] = "/Catalog/ChildObjects/Form[0]"
    inventory["objects"].append(child)

    with pytest.raises(CoreError) as error:
        plan_edt_identity_three_way(inventory, inventory, inventory)
    assert error.value.code == "EDT_IDENTITY_PLAN_INVALID"
