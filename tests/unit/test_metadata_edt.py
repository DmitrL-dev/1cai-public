"""EDT .mdo metadata is parsed with the same bounded read projections."""

from dataclasses import dataclass
from types import SimpleNamespace


from rentgen_core.context import SnapshotRef
from rentgen_core.metadata import (
    MetadataLimits,
    _candidate,
    _load,
    _named,
    _nested_assets,
    _preview,
)
from rentgen_core.metadata_xml import parse_xml
from rentgen_core.source_configuration import SourceLayerSpec
from rentgen_core.sources import SourceRef


PROJECT = "12345678-1234-4234-8234-123456789abc"
SNAPSHOT = SnapshotRef(PROJECT, "a" * 64, "a" * 64)
LAYER = SourceLayerSpec("base", 0, "base", ".", "edt")
UNKNOWN_LAYER = SourceLayerSpec("base", 0, "base", ".", "unknown")

CATALOG = b"""<?xml version="1.0" encoding="UTF-8"?>
<mdclass:Catalog xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass"
    uuid="11111111-1111-4111-8111-111111111111">
  <name>Products</name>
  <attributes uuid="22222222-2222-4222-8222-222222222222">
    <name>Article</name>
    <type><types>String</types><stringQualifiers><length>32</length></stringQualifiers></type>
  </attributes>
  <forms uuid="33333333-3333-4333-8333-333333333333"><name>ItemForm</name></forms>
</mdclass:Catalog>"""
CONFIGURATION = b"""<?xml version="1.0" encoding="UTF-8"?>
<mdclass:Configuration xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass"
    uuid="44444444-4444-4444-8444-444444444444"><name>RentgenMD</name></mdclass:Configuration>"""
FORM = """<?xml version="1.0" encoding="UTF-8"?>
<form:Form xmlns:form="http://g5.1c.ru/v8/dt/form">
  <items><name>Article</name><dataPath><segments>Объект.Article</segments></dataPath></items>
</form:Form>""".encode(
    "utf-8"
)


@dataclass
class Entry:
    ref: SourceRef
    raw: bytes
    encoding: str = "utf-8"

    @property
    def size_bytes(self):
        return len(self.raw)


class Session:
    validation_summary = {"status": "verified"}

    def __init__(self, entries):
        self._entries = tuple(entries)

    def entries(self):
        return self._entries

    def checkpoint(self):
        return None


class Reader:
    def __init__(self, entries):
        self.session = Session(entries)
        self.limits = MetadataLimits()
        self.verified = []

    def xml(self, entry):
        self.verified.append(entry.ref)
        return parse_xml(
            entry.raw,
            max_bytes=self.limits.max_xml_bytes,
            max_nodes=self.limits.max_nodes,
            max_depth=self.limits.max_depth,
        )

    def bytes(self, entry, *, xml=False):
        self.verified.append(entry.ref)
        return entry.raw


def entry(path, raw):
    return Entry(SourceRef(SNAPSHOT, "base", path, "0" * 64), raw)


def context():
    return SimpleNamespace(snapshot=SNAPSHOT)


def test_candidate_recognizes_edt_mdo_paths():
    assert _candidate("Configuration/Configuration.mdo") == "Configuration"
    assert _candidate("Catalogs/Products/Products.mdo") == "Catalog"
    assert _candidate("Catalogs/Products/other.mdo") is None
    assert _candidate("Catalogs/Products/Products.xml") == "Catalog"


def test_load_parses_edt_object_and_form_with_source_refs():
    entries = [
        entry("Configuration/Configuration.mdo", CONFIGURATION),
        entry("Catalogs/Products/Products.mdo", CATALOG),
        entry("Catalogs/Products/Forms/ItemForm/Form.form", FORM),
    ]
    reader = Reader(entries)

    envelope, selected, _ = _load(
        context(), [LAYER], reader, object_path=entries[1].ref.relative_path
    )

    assert envelope["layers"][0]["status"] == "supported"
    assert envelope["layers"][0]["format_decision"]["detected"] == "edt_mdo"
    assert envelope["parser_profiles"] == ["edt_mdo_v1"]
    assert (
        envelope["layers"][0]["format_decision"]["scan"]["opaque_mdo"]["status"]
        == "parsed"
    )
    assert (
        envelope["validation_summary"]["metadata_scan"][
            "all_selected_candidates_examined"
        ]
        is True
    )
    assert selected is not None
    _, catalog, kind = selected
    assert kind == "Catalog"
    assert catalog.attrib["uuid"] == "11111111-1111-4111-8111-111111111111"
    preview = _preview(entries[1], catalog, kind)
    assert preview["name"] == "Products"
    assert (
        _named(catalog, "Attribute", preview["source_ref"], 10)["items"][0]["name"]
        == "Article"
    )
    assert (
        _named(catalog, "Form", preview["source_ref"], 10)["items"][0]["name"]
        == "ItemForm"
    )
    assets = _nested_assets(entries[1], entries, reader, 10)
    assert assets["form_documents"]["total"] == 1
    assert assets["form_documents"]["items"][0]["fields"]["total"] == 2

    object_result = envelope["layers"][0]
    assert object_result["inventory_counts"]["objects"] == 1


def test_edt_parse_rejects_path_root_mismatch():
    entries = [entry("Catalogs/Products/Products.mdo", CONFIGURATION)]
    reader = Reader(entries)
    envelope, selected, _ = _load(
        context(), [LAYER], reader, object_path=entries[0].ref.relative_path
    )
    assert envelope["layers"][0]["status"] == "unsupported"
    assert selected is None


def test_mdo_without_explicit_edt_declaration_stays_opaque():
    entries = [entry("Catalogs/Products/Products.mdo", CATALOG)]
    reader = Reader(entries)
    envelope, selected, _ = _load(
        context(), [UNKNOWN_LAYER], reader, object_path=entries[0].ref.relative_path
    )

    layer = envelope["layers"][0]
    assert layer["status"] == "unsupported"
    assert selected is None
    assert layer["format_decision"]["scan"]["xml_candidates"]["status"] == (
        "skipped_unsupported_format"
    )
    assert layer["format_decision"]["scan"]["opaque_mdo"]["status"] == (
        "verified_bytes"
    )
    assert layer["format_decision"]["scan"]["opaque_mdo"]["verified_count"] == 1
    assert envelope["parser_profiles"] == []
