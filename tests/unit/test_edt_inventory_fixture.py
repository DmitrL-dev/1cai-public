"""Synthetic read-contract matrix; no EDT/1C execution or native acceptance.

The cases and expected identities are declared independently of runtime type
maps. Reuse only the existing in-memory capability and XML construction helpers.
"""

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

import pytest

from rentgen_core import edt_inventory as edt
from rentgen_core.errors import CoreError
from rentgen_core.metadata_three_way import (
    materialize_metadata_three_way,
    plan_metadata_three_way,
)
from rentgen_core.source_configuration import SourceLayerSpec
from test_edt_inventory_metadata import (
    BASE,
    CHILD_UUID,
    CONFIG_UUID,
    NS,
    OBJECT_UUID,
    PATH,
    context,
    entry,
    mdo,
)


FIXTURE = Path(__file__).resolve().parents[2] / "packaging/fixtures/edt-inventory-v1"


@pytest.fixture
def corpus():
    manifest = json.loads((FIXTURE / "manifest.json").read_text("utf-8"))
    assert manifest["schema"] == 1
    assert manifest["fixture"] == "edt-inventory-v1"
    assert manifest["provenance"] == "synthetic"
    assert manifest["scope"] == "read_only_contract"
    assert manifest["native_execution"] is False
    assert manifest["live_acceptance"] is False
    assert manifest["cf_cfe_acceptance"] is False
    records = manifest["files"]
    paths = [record["path"] for record in records]
    assert len(paths) == len(set(paths)) == 20
    assert set(paths) == {
        path.relative_to(FIXTURE).as_posix()
        for folder in (FIXTURE / "base", FIXTURE / "negative")
        for path in folder.rglob("*")
        if path.is_file()
    }
    for record in records:
        raw = (FIXTURE / record["path"]).read_bytes()
        assert len(raw) == record["size_bytes"]
        assert sha256(raw).hexdigest() == record["sha256"]
    return manifest


@pytest.mark.parametrize("reverse", [False, True], ids=["manifest-order", "reversed"])
def test_saved_corpus_matches_independent_identity_owner_layer_and_hash_expectations(
    corpus, reverse
):
    files = [
        entry(
            record["path"].removeprefix("base/"),
            (FIXTURE / record["path"]).read_bytes(),
        )
        for record in corpus["files"]
        if record["role"] in {"mdo", "opaque"}
    ]
    if reverse:
        files.reverse()
    configuration = next(
        item
        for item in files
        if item.ref.relative_path == "Configuration/Configuration.mdo"
    )
    ctx = context([item for item in files if item is not configuration])
    # The shared helper supplies exactly this saved Configuration, not a
    # second descriptor or an unrelated hidden source.
    assert ctx.sources.entries()[0].raw == configuration.raw
    original = ctx.sources.read_source

    def read_mdo_only(ref):
        assert ref.relative_path.endswith(".mdo"), "Opaque fixture bytes were read"
        return original(ref)

    ctx.sources.read_source = read_mdo_only
    result = edt.edt_metadata_inventory(ctx)
    expected = corpus["expected"]
    assert result["parser"] == expected["parser"] == "edt_identity_v1"
    assert result["coverage"] == expected["coverage"] == "partial"
    assert result["layers"] == [
        {
            **corpus["layer"],
            "parsed_mdo_files": expected["parsed_mdo_files"],
            "unparsed_files": expected["unparsed_files"],
            "count_basis": "verified_manifest_paths",
        }
    ]
    assert corpus["layer"] == asdict(BASE)
    assert len(result["objects"]) == expected["identity_count"] == 17
    refs = {
        item.ref.relative_path: asdict(item.ref)
        for item in files
        if item.ref.relative_path.endswith(".mdo")
    }
    expected_objects = []
    for row in expected["objects"]:
        ref = refs[row["path"]]
        owner = row["owner"]
        expected_objects.append(
            {
                **{
                    key: value
                    for key, value in row.items()
                    if key not in {"path", "owner"}
                },
                "layer": corpus["layer"],
                "source_ref": ref,
                "owner": None if owner is None else {**owner, "source_ref": ref},
            }
        )
    assert sorted(result["objects"], key=lambda row: row["canonical_uuid"]) == sorted(
        expected_objects, key=lambda row: row["canonical_uuid"]
    )
    assert sorted(
        result["source_refs"], key=lambda ref: ref["relative_path"]
    ) == sorted(refs.values(), key=lambda ref: ref["relative_path"])
    assert len(refs) == expected["parsed_mdo_files"] == 9
    assert expected["unparsed_files"] == 5


@pytest.mark.parametrize(
    "filename,code",
    [
        ("malformed.mdo", "XML_INVALID"),
        ("foreign-namespace.mdo", "EDT_INVENTORY_UNSUPPORTED"),
        ("invalid-uuid.mdo", "EDT_IDENTITY_INVALID"),
        ("missing-name.mdo", "EDT_IDENTITY_INVALID"),
        ("unknown-extension.mdo", "EDT_INVENTORY_UNSUPPORTED"),
        ("dtd.mdo", "XML_FORBIDDEN"),
    ],
)
def test_saved_negative_corpus_fails_closed(corpus, filename, code):
    case = next(
        row for row in corpus["negative_cases"] if row["path"] == "negative/" + filename
    )
    assert case["expected_error"] == code
    source = entry(case["source_path"], (FIXTURE / case["path"]).read_bytes())
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(context([source]))
    assert error.value.code == code
    assert set(error.value.details) == {"source_ref"}
    assert error.value.details["source_ref"] == asdict(source.ref)


# Paths and expected types are a fixed representative corpus, not a reflection
# of FOLDER_TO_TYPE or a claim that these minimal objects compile in 1C.
ROOT_CASES = (
    ("Configuration/Configuration.mdo", "Configuration", "Demo", CONFIG_UUID),
    (PATH, "Catalog", "Products", OBJECT_UUID),
    ("Documents/Order/Order.mdo", "Document", "Order", OBJECT_UUID),
    (
        "InformationRegisters/Prices/Prices.mdo",
        "InformationRegister",
        "Prices",
        OBJECT_UUID,
    ),
    ("Enums/State/State.mdo", "Enum", "State", OBJECT_UUID),
    ("CommonModules/Helpers/Helpers.mdo", "CommonModule", "Helpers", OBJECT_UUID),
    ("CommonForms/Search/Search.mdo", "CommonForm", "Search", OBJECT_UUID),
    ("Reports/Sales/Sales.mdo", "Report", "Sales", OBJECT_UUID),
    ("CommonTemplates/Layout/Layout.mdo", "CommonTemplate", "Layout", OBJECT_UUID),
)


@pytest.mark.parametrize("path,kind,name,identity", ROOT_CASES)
def test_representative_root_identity_contract(path, kind, name, identity):
    source = entry(path, mdo(kind, name, identity))
    ctx = context([] if kind == "Configuration" else [source])
    result = edt.edt_metadata_inventory(ctx)
    selected = [obj for obj in result["objects"] if obj["canonical_uuid"] == identity]

    assert selected == [
        {
            "canonical_uuid": identity,
            "observed_uuid": identity,
            "type": kind,
            "name": name,
            "xml_path": "/" + kind,
            "owner": None,
            "layer": asdict(BASE),
            "source_ref": asdict(source.ref),
        }
    ]
    assert result["parser"] == "edt_identity_v1"
    assert result["coverage"] == "partial"
    assert result["owner_basis"] == "direct_xml_containment_only"
    assert result["layer_basis"] == "pinned_snapshot_declaration"
    assert asdict(source.ref) in result["source_refs"]


CHILD_CASES = (
    (PATH, "Catalog", "Products", "attributes", "Attribute", "Article"),
    (
        "Documents/Order/Order.mdo",
        "Document",
        "Order",
        "tabularSections",
        "TabularSection",
        "Lines",
    ),
    (
        "InformationRegisters/Prices/Prices.mdo",
        "InformationRegister",
        "Prices",
        "dimensions",
        "Dimension",
        "Product",
    ),
    (
        "InformationRegisters/Prices/Prices.mdo",
        "InformationRegister",
        "Prices",
        "resources",
        "Resource",
        "Price",
    ),
    (PATH, "Catalog", "Products", "forms", "Form", "ItemForm"),
    (PATH, "Catalog", "Products", "commands", "Command", "OpenItem"),
    ("Enums/State/State.mdo", "Enum", "State", "enumValues", "EnumValue", "New"),
)


@pytest.mark.parametrize("qualified", [False, True], ids=["plain", "metadata-ns"])
@pytest.mark.parametrize("path,kind,name,tag,child_kind,child_name", CHILD_CASES)
def test_embedded_declaration_matrix(
    qualified, path, kind, name, tag, child_kind, child_name
):
    prefix = "md:" if qualified else ""
    # A property before the declaration proves XML indexes count all children.
    children = (
        "<comment>synthetic</comment>"
        f'<{prefix}{tag} uuid="{CHILD_UUID}">'
        f"<{prefix}name>{child_name}</{prefix}name></{prefix}{tag}>"
    )
    source = entry(path, mdo(kind, name, children=children))
    result = edt.edt_metadata_inventory(context([source]))
    selected = [obj for obj in result["objects"] if obj["canonical_uuid"] == CHILD_UUID]

    assert selected == [
        {
            "canonical_uuid": CHILD_UUID,
            "observed_uuid": CHILD_UUID,
            "type": child_kind,
            "name": child_name,
            "xml_path": f"/{kind}/{tag}[2]",
            "owner": {
                "canonical_uuid": OBJECT_UUID,
                "source_ref": asdict(source.ref),
                "xml_path": "/" + kind,
            },
            "layer": asdict(BASE),
            "source_ref": asdict(source.ref),
        }
    ]
    assert result["layers"][0]["parsed_mdo_files"] == 2
    assert result["layers"][0]["unparsed_files"] == 0


@pytest.mark.parametrize(
    "path",
    [
        "Catalogs/Products/Forms/ItemForm/Form.form",
        "CommonModules/Helpers/Module.bsl",
        "Reports/Sales/Templates/Layout/Ext/Template.xml",
        "configuration.cf",
        "extension.cfe",
    ],
    ids=["edt-form", "bsl", "data-composition-schema", "cf", "cfe"],
)
def test_non_mdo_assets_are_counted_without_reading_or_claiming_content(path):
    source = entry(PATH, mdo())
    # Deliberately invalid bytes: even malformed XML/binary data must not be
    # parsed by the identity inventory, which has only a path-count contract.
    asset = entry(path, b"\xff\x00<!DOCTYPE not-a-valid-asset>")
    ctx = context([source, asset])
    original = ctx.sources.read_source

    def read_mdo_only(ref):
        assert ref.relative_path != path, "Inventory read an opaque asset"
        return original(ref)

    ctx.sources.read_source = read_mdo_only
    result = edt.edt_metadata_inventory(ctx)
    assert result["layers"][0]["parsed_mdo_files"] == 2
    assert result["layers"][0]["unparsed_files"] == 1
    assert result["layers"][0]["count_basis"] == "verified_manifest_paths"
    assert {ref["relative_path"] for ref in result["source_refs"]} == {
        "Configuration/Configuration.mdo",
        PATH,
    }
    assert asdict(asset.ref) not in result["source_refs"]
    assert result["coverage"] == "partial"


@pytest.mark.parametrize("source_format", ["cf", "cfe"])
def test_binary_containers_cannot_be_registered_as_a_source_format(source_format):
    with pytest.raises(CoreError) as error:
        SourceLayerSpec("base", 0, "base", ".", source_format)
    assert error.value.code == "SOURCE_LAYER_INVALID"


@pytest.mark.parametrize(
    "name", ["", " Article", "Article ", "1Article", "A" * 257, "<part>Article</part>"]
)
def test_invalid_embedded_names_do_not_produce_an_inventory(name):
    raw = mdo(
        children=f'<attributes uuid="{CHILD_UUID}"><name>{name}</name></attributes>'
    )
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(context([entry(PATH, raw)]))
    assert error.value.code == "EDT_IDENTITY_INVALID"


@pytest.mark.parametrize("name", ["A" * 256, "Артикул"])
def test_name_boundary_and_cyrillic_are_preserved(name):
    raw = mdo(
        children=f'<attributes uuid="{CHILD_UUID}"><name>{name}</name></attributes>'
    )
    result = edt.edt_metadata_inventory(context([entry(PATH, raw)]))
    child = next(
        obj for obj in result["objects"] if obj["canonical_uuid"] == CHILD_UUID
    )
    assert child["name"] == name


def test_same_child_name_under_distinct_owners_keeps_distinct_identities():
    other_uuid = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
    other_child_uuid = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
    files = [
        entry(
            PATH,
            mdo(
                children=f'<attributes uuid="{CHILD_UUID}"><name>Code</name></attributes>'
            ),
        ),
        entry(
            "Catalogs/Other/Other.mdo",
            mdo(
                name="Other",
                uuid=other_uuid,
                children=f'<attributes uuid="{other_child_uuid}"><name>Code</name></attributes>',
            ),
        ),
    ]
    result = edt.edt_metadata_inventory(context(files))
    assert {
        (obj["canonical_uuid"], obj["owner"]["canonical_uuid"])
        for obj in result["objects"]
        if obj["name"] == "Code"
    } == {(CHILD_UUID, OBJECT_UUID), (other_child_uuid, other_uuid)}
    assert result == edt.edt_metadata_inventory(context(list(reversed(files))))


# Disjoint roots match a registerable layer declaration; UUIDs intentionally
# repeat between these two layers without establishing extension ownership.
BASE_LAYER = SourceLayerSpec("base", 0, "base", "base", "edt")
EXTENSION_LAYER = SourceLayerSpec("extra", 1, "extension", "extension", "edt")


def layered_context():
    return context(
        [entry(PATH, mdo()), entry(PATH, mdo(), "extra")],
        (BASE_LAYER, EXTENSION_LAYER),
    )


def test_extension_layer_is_only_a_separate_identity_observation():
    result = edt.edt_metadata_inventory(layered_context())
    roots = [obj for obj in result["objects"] if obj["canonical_uuid"] == OBJECT_UUID]
    assert len(roots) == 2
    for row, layer in zip(roots, (BASE_LAYER, EXTENSION_LAYER)):
        assert row["layer"] == asdict(layer)
        assert row["owner"] is None
        assert row["source_ref"]["layer_id"] == layer.layer_id
        assert set(row) == {
            "canonical_uuid",
            "observed_uuid",
            "type",
            "name",
            "xml_path",
            "owner",
            "layer",
            "source_ref",
        }
    assert result["coverage"] == "partial"
    assert result["identity_scope"] == "snapshot_layer"
    assert result["owner_basis"] == "direct_xml_containment_only"


@pytest.mark.parametrize("budget", ["max_mdo_files", "max_identities"])
def test_inventory_budgets_apply_across_selected_layers(budget):
    # Each selected layer has two identities/documents. Three permits either
    # layer alone and must still reject their combined operation.
    limits = edt.EDTInventoryLimits(**{budget: 3})
    for layer in ("base", "extra"):
        result = edt.edt_metadata_inventory(
            layered_context(), layer_id=layer, limits=limits
        )
        assert len(result["objects"]) == 2
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(layered_context(), limits=limits)
    assert error.value.code == "METADATA_LIMIT_EXCEEDED"


@pytest.mark.parametrize(
    "declaration",
    [
        f'<adoptedObject uuid="{CHILD_UUID}"><name>Borrowed</name></adoptedObject>',
        f'<extendedConfigurationObject><target uuid="{CHILD_UUID}"/></extendedConfigurationObject>',
    ],
)
def test_unknown_extension_identity_declarations_fail_closed(declaration):
    ctx = context(
        [entry(PATH, mdo(children=declaration), "extra")],
        (BASE_LAYER, EXTENSION_LAYER),
    )
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(ctx)
    assert error.value.code == "EDT_INVENTORY_UNSUPPORTED"


@pytest.mark.parametrize(
    "declaration",
    [
        "<ObjectBelonging>Adopted</ObjectBelonging>",
        "<ExtendedConfigurationObject>Catalog.Products</ExtendedConfigurationObject>",
        "<ConfigurationExtensionPurpose>Customization</ConfigurationExtensionPurpose>",
    ],
)
def test_designer_extension_declarations_block_even_an_unchanged_candidate(declaration):
    # Separate Designer semantics API: recognizing an EDT layer above must not
    # be mistaken for qualification of these extension declarations.
    raw = (
        '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">'
        f'<Catalog uuid="{OBJECT_UUID}"><Properties><Name>Products</Name>'
        f"{declaration}</Properties><ChildObjects/></Catalog></MetaDataObject>"
    ).encode()
    tree = {"Catalogs/Products.xml": raw}
    result = plan_metadata_three_way(tree, tree, tree)
    scopes = result["semantics"]["scopes"]
    assert len(scopes) == 1
    assert scopes[0]["kind"] == "extension"
    assert scopes[0]["action"] == "unchanged"
    assert scopes[0]["status"] == "unsupported"
    assert scopes[0]["reason"] == "extension_ownership_unverified"
    with pytest.raises(CoreError) as error:
        materialize_metadata_three_way(tree, tree, tree)
    assert error.value.code == "THREE_WAY_CONFLICT"


def test_late_unsupported_document_does_not_return_partial_inventory():
    first = entry(PATH, mdo())
    last = entry(
        "Reports/Sales/Sales.mdo",
        mdo("Report", "Sales").replace(NS.encode(), b"urn:unknown"),
    )
    ctx = context([first, last])
    with pytest.raises(CoreError) as error:
        edt.edt_metadata_inventory(ctx)
    assert error.value.code == "EDT_INVENTORY_UNSUPPORTED"
    assert first.ref in ctx.sources.reads
    assert last.ref in ctx.sources.reads
    assert set(error.value.details) == {"source_ref"}
