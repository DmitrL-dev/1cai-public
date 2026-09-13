"""Snapshot EDT inventory binds identities to verified bytes and declared layers."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
from types import SimpleNamespace

import pytest

from rentgen_core import edt_inventory as edt
from rentgen_core.context import SnapshotRef
from rentgen_core.errors import CoreError
from rentgen_core.source_configuration import SourceLayerSpec
from rentgen_core.sources import SourceRef


SNAPSHOT = SnapshotRef("12345678-1234-4234-8234-123456789abc", "a" * 64, "a" * 64)
BASE = SourceLayerSpec("base", 0, "base", ".", "edt")
EXTENSION = SourceLayerSpec("extra", 1, "extension", "extensions/Extra", "edt")
CONFIG_UUID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OBJECT_UUID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
CHILD_UUID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
NS = "http://g5.1c.ru/v8/dt/metadata/mdclass"
PATH = "Catalogs/Products/Products.mdo"


def mdo(kind="Catalog", name="Products", uuid=OBJECT_UUID, children=""):
    return (
        f'<md:{kind} xmlns:md="{NS}" uuid="{uuid}">'
        f"<name>{name}</name>{children}</md:{kind}>"
    ).encode()


@dataclass
class Entry:
    ref: SourceRef
    raw: bytes

    @property
    def size_bytes(self):
        return len(self.raw)


def entry(path, raw, layer="base"):
    return Entry(SourceRef(SNAPSHOT, layer, path, sha256(raw).hexdigest()), raw)


def context(files, layers=(BASE,)):
    """Exercise the public authorization/session path with an in-memory capability."""
    entries = [
        entry(
            "Configuration/Configuration.mdo",
            mdo("Configuration", "Demo", CONFIG_UUID),
            layer.layer_id,
        )
        for layer in layers
    ] + files

    class Capability:
        validation_summary = {"status": "verified"}
        revoked = False
        reads = []

        def checkpoint(self):
            if self.revoked:
                raise CoreError("FORBIDDEN", "Revoked")

        @contextmanager
        def transaction(self, principal):
            yield self

        def require_all(self, permissions):
            assert permissions == {"project:read"}
            self.checkpoint()

        def get_snapshot_layers(self, snapshot_id):
            assert snapshot_id == SNAPSHOT.snapshot_id
            return layers

        @contextmanager
        def read_session(self, *, limits):
            self.checkpoint()
            yield self

        def entries(self):
            return tuple(entries)

        def read_source(self, ref):
            self.checkpoint()
            self.reads.append(ref)
            return next(item.raw for item in entries if item.ref == ref)

    capability = Capability()
    return SimpleNamespace(
        snapshot=SNAPSHOT, principal="test", state=capability, sources=capability
    )


def test_inventory_canonical_identity_owner_and_layer_evidence():
    raw = mdo(
        uuid=OBJECT_UUID.upper(),
        children=f'<attributes uuid="{CHILD_UUID}"><name>Article</name></attributes>',
    )
    source = entry(PATH, raw)
    result = edt.edt_metadata_inventory(context([source]))

    assert result["parser"] == "edt_identity_v1"
    assert result["identity_scope"] == "snapshot_layer"
    assert result["coverage"] == "partial"
    objects = {obj["canonical_uuid"]: obj for obj in result["objects"]}
    root = objects[OBJECT_UUID]
    child = objects[CHILD_UUID]
    assert root["observed_uuid"] == OBJECT_UUID.upper()
    assert root["owner"] is None
    assert root["layer"] == asdict(BASE)
    assert root["source_ref"] == asdict(source.ref)
    assert child["type"] == "Attribute"
    assert child["owner"] == {
        "canonical_uuid": OBJECT_UUID,
        "source_ref": asdict(source.ref),
        "xml_path": "/Catalog",
    }
    assert child["xml_path"] == "/Catalog/attributes[1]"
    assert result["validation_summary"]["generation"] == {"status": "verified"}


@pytest.mark.parametrize(
    "uuid",
    [
        "",
        "bad",
        "{bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb}",
        "b" * 32,
        "00000000-0000-0000-0000-000000000000",
    ],
)
def test_invalid_uuid_fails_closed(uuid):
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(context([entry(PATH, mdo(uuid=uuid))]))
    assert error.value.code == "EDT_IDENTITY_INVALID"


@pytest.mark.parametrize("nested", [False, True])
def test_duplicate_uuid_is_rejected_after_normalization(nested):
    files = [entry(PATH, mdo())]
    if nested:
        files = [
            entry(
                PATH,
                mdo(
                    children=f'<attributes uuid="{OBJECT_UUID.upper()}"><name>Article</name></attributes>'
                ),
            )
        ]
    else:
        files.append(
            entry(
                "Catalogs/Other/Other.mdo", mdo(name="Other", uuid=OBJECT_UUID.upper())
            )
        )
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(context(files))
    assert error.value.code == "EDT_IDENTITY_DUPLICATE"


def test_uuid_is_scoped_to_layer_and_selection_excludes_other_layers():
    ctx = context([entry(PATH, mdo()), entry(PATH, mdo(), "extra")], (BASE, EXTENSION))
    result = edt.edt_metadata_inventory(ctx)
    objects = [obj for obj in result["objects"] if obj["canonical_uuid"] == OBJECT_UUID]
    assert [obj["layer"]["kind"] for obj in objects] == ["base", "extension"]
    selected = edt.edt_metadata_inventory(ctx, layer_id="extra")
    assert all(obj["layer"]["layer_id"] == "extra" for obj in selected["objects"])


@pytest.mark.parametrize(
    "path,raw,code",
    [
        (PATH, mdo("Document"), "EDT_INVENTORY_UNSUPPORTED"),
        (PATH, mdo(name="Different"), "EDT_IDENTITY_INVALID"),
        (PATH, mdo().replace(NS.encode(), b"urn:other"), "EDT_INVENTORY_UNSUPPORTED"),
        (PATH, mdo(children="<name>Again</name>"), "EDT_IDENTITY_INVALID"),
        (
            PATH,
            mdo(children="<attributes><name>Article</name></attributes>"),
            "EDT_IDENTITY_INVALID",
        ),
        (
            PATH,
            mdo(
                children=f'<unknown uuid="{CHILD_UUID}"><name>Unknown</name></unknown>'
            ),
            "EDT_INVENTORY_UNSUPPORTED",
        ),
        ("Unknown/X/X.mdo", mdo(), "EDT_INVENTORY_UNSUPPORTED"),
        ("Catalogs/Products.xml", mdo(), "EDT_INVENTORY_UNSUPPORTED"),
    ],
)
def test_unsupported_or_ambiguous_identity_is_never_skipped(path, raw, code):
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(context([entry(path, raw)]))
    assert error.value.code == code


def test_unparsed_assets_are_reported_as_manifest_counts_only():
    result = edt.edt_metadata_inventory(
        context([entry(PATH, mdo()), entry("Catalogs/Products/Module.bsl", b"opaque")])
    )
    assert result["layers"][0]["unparsed_files"] == 1
    assert all(ref["relative_path"].endswith(".mdo") for ref in result["source_refs"])


@pytest.mark.parametrize(
    "options",
    [
        {"max_mdo_files": 1},
        {"max_identities": 1},
        {"max_xml_bytes": 10},
        {"max_total_bytes": 10},
        {"max_nodes": 1},
        {"max_depth": 1},
        {"max_inventory": 1},
    ],
)
def test_each_inventory_budget_fails_closed(options):
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(
            context([entry(PATH, mdo())]), limits=edt.EDTInventoryLimits(**options)
        )
    assert error.value.code == "METADATA_LIMIT_EXCEEDED"


@pytest.mark.parametrize(
    "options",
    [
        {"max_identities": True},
        {"max_mdo_files": 0},
        {"max_identities": 20001},
        {"max_xml_bytes": 4 * 1024 * 1024 + 1},
    ],
)
def test_inventory_limits_are_typed_and_bounded(options):
    with pytest.raises(CoreError) as error:
        edt.EDTInventoryLimits(**options)
    assert error.value.code == "INVALID_QUERY_OPTIONS"


def test_explicit_edt_layer_required():
    layer = SourceLayerSpec("base", 0, "base", ".", "unknown")
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(context([entry(PATH, mdo())], (layer,)))
    assert error.value.code == "EDT_INVENTORY_UNSUPPORTED"


def test_revocation_propagates_without_source_details():
    ctx = context([entry(PATH, mdo())])
    original = ctx.sources.read_source

    def revoke(ref):
        raw = original(ref)
        ctx.sources.revoked = True
        return raw

    ctx.sources.read_source = revoke
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(ctx)
    assert error.value.code == "FORBIDDEN"
    assert error.value.details == {}


def test_revocation_during_identity_error_reauthenticates_before_propagation(
    monkeypatch,
):
    ctx = context([entry(PATH, mdo())])

    def revoke_then_fail(node, kind, xml_path, owner, layer, ref):
        ctx.sources.revoked = True
        raise CoreError(
            "EDT_IDENTITY_INVALID",
            "Invalid identity",
            details={"source_ref": ref},
        )

    monkeypatch.setattr(edt, "_edt_identity", revoke_then_fail)
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(ctx)
    assert error.value.code == "FORBIDDEN"
    assert error.value.details == {}


def test_dtd_is_rejected_by_shared_bounded_parser():
    raw = b'<!DOCTYPE Catalog [<!ENTITY x "unsafe">]>' + mdo()
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(context([entry(PATH, raw)]))
    assert error.value.code == "XML_FORBIDDEN"


@pytest.mark.parametrize(
    "children",
    [
        f'<x:attributes xmlns:x="urn:other" uuid="{CHILD_UUID}"><name>Article</name></x:attributes>',
        f'<attributes uuid="{CHILD_UUID}"><x:name xmlns:x="urn:other">Article</x:name></attributes>',
        f'<other xmlns:x="urn:other" x:uuid="{CHILD_UUID}"/>',
        f'<attributes uuid="{CHILD_UUID}"><name>Article</name><forms uuid="dddddddd-dddd-4ddd-8ddd-dddddddddddd"><name>InvalidOwner</name></forms></attributes>',
    ],
)
def test_unknown_namespace_or_unsupported_owner_fails_closed(children):
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(context([entry(PATH, mdo(children=children))]))
    assert error.value.code in {"EDT_INVENTORY_UNSUPPORTED", "EDT_IDENTITY_INVALID"}


def test_nested_owner_is_the_immediate_tabular_section():
    section_uuid = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
    raw = mdo(
        children=f'<tabularSections uuid="{section_uuid}"><name>Lines</name><attributes uuid="{CHILD_UUID}"><name>Article</name></attributes></tabularSections>'
    )
    result = edt.edt_metadata_inventory(context([entry(PATH, raw)]))
    child = next(
        obj for obj in result["objects"] if obj["canonical_uuid"] == CHILD_UUID
    )
    assert child["owner"]["canonical_uuid"] == section_uuid
    assert child["owner"]["xml_path"] == "/Catalog/tabularSections[1]"


def test_same_name_and_type_under_one_owner_is_ambiguous():
    children = f'<attributes uuid="{CHILD_UUID}"><name>Article</name></attributes><attributes uuid="dddddddd-dddd-4ddd-8ddd-dddddddddddd"><name>ARTICLE</name></attributes>'
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(context([entry(PATH, mdo(children=children))]))
    assert error.value.code == "EDT_IDENTITY_DUPLICATE"


def test_unknown_selected_layer_and_missing_context_keep_shared_errors():
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(context([]), layer_id="missing")
    assert error.value.code == "SOURCE_LAYER_NOT_FOUND"
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(None)
    assert error.value.code == "CONTEXT_REQUIRED"
