"""GUI-only bounded Designer child-field matching, not a semantic index."""
import time

from .errors import CoreError
from .metadata import _local

FIELD_LIMIT = 20_000
MATCH_LIMIT = 20
TEXT_BYTES = 512
CPU_SECONDS = 10
WALL_SECONDS = 45
SCOPE = "designer_direct_fields_and_tabular_attributes"


class FieldSearch:
    def __init__(self, authorize):
        self.authorize = authorize
        self.wall = time.monotonic()
        self.cpu = time.thread_time()
        self.fields = self.sections = 0

    def checkpoint(self):
        self.authorize()
        if time.monotonic() - self.wall >= WALL_SECONDS or time.thread_time() - self.cpu >= CPU_SECONDS:
            raise CoreError("METADATA_SEARCH_BUDGET_EXCEEDED", "Metadata field search did not complete within its budget")

    def short(self, value):
        if value is not None and len(value.encode("utf-8")) > TEXT_BYTES:
            raise CoreError("METADATA_SEARCH_LIMIT_EXCEEDED", "Metadata field text exceeds search output bounds")
        return value

    def count(self, section=False):
        if section:
            self.sections += 1
        else:
            self.fields += 1
        if self.fields + self.sections > FIELD_LIMIT:
            raise CoreError("METADATA_SEARCH_LIMIT_EXCEEDED", "Metadata field inventory exceeds search bounds")

    def single(self, node, name):
        if node is None:
            return None
        found = None
        for child in node:
            self.checkpoint()
            if _local(child.tag).casefold() == name.casefold():
                if found is not None:
                    raise CoreError("METADATA_SEARCH_UNSUPPORTED", "Ambiguous duplicate metadata field structure")
                found = child
        return found

    def text(self, node, name):
        child = self.single(node, name)
        if child is None:
            return None
        if len(child):
            raise CoreError("METADATA_SEARCH_UNSUPPORTED", "Metadata field text contains unsupported nested elements")
        return self.short((child.text or "").strip() or None)

    def synonym(self, props, term):
        node = self.single(props, "Synonym")
        if node is None:
            return None, None, False
        first = preferred = matched = None
        # Designer localized strings consist of direct item/lang/content records.
        # Do not recursively consume unrelated descendants as synonym evidence.
        if not len(node):
            value = self.short((node.text or "").strip() or None)
            return value, None, bool(value and term in value.casefold())
        for item in node:
            self.checkpoint()
            if _local(item.tag) != "item":
                raise CoreError("METADATA_SEARCH_UNSUPPORTED", "Unsupported localized metadata field structure")
            locale = self.text(item, "lang")
            value = self.text(item, "content")
            if not value:
                continue
            candidate = (value, locale)
            if first is None:
                first = candidate
            if preferred is None and locale == "ru":
                preferred = candidate
            if matched is None and term in value.casefold():
                matched = candidate
        chosen = matched or preferred or first or (None, None)
        return *chosen, matched is not None

    def match(self, meta, term):
        matches, total = [], 0
        owner_props = self.single(meta, "Properties")
        self.single(owner_props, "Name")
        self.single(owner_props, "Synonym")
        children = self.single(meta, "ChildObjects")
        if children is None:
            return matches, total

        def field(node, index, parent=None, parent_index=None):
            nonlocal total
            self.checkpoint()
            self.count()
            props = self.single(node, "Properties")
            # A malformed known field is not silently treated as absent.
            if props is None:
                raise CoreError("METADATA_SEARCH_UNSUPPORTED", "Known metadata field has no Properties")
            parent_props = self.single(parent, "Properties") if parent is not None else None
            synonym, locale, synonym_match = self.synonym(props, term)
            row = {
                "type": _local(node.tag),
                "name": self.text(props, "Name"),
                "synonym": synonym, "synonym_locale": locale,
                "parent_name": self.text(parent_props, "Name"),
                "parent_type": "TabularSection" if parent is not None else None,
                "observed_uuid": self.short(node.attrib.get("uuid")),
                "uuid_status": "unverified", "child_index": index,
                "parent_index": parent_index,
            }
            # Parent name is context, not itself a child-field match.
            if synonym_match or any(term in (row[key] or "").casefold() for key in ("name", "type")):
                total += 1
                if len(matches) < MATCH_LIMIT:
                    matches.append(row)

        for index, node in enumerate(children, 1):
            self.checkpoint()
            kind = _local(node.tag)
            if kind in {"Attribute", "Dimension", "Resource"}:
                field(node, index)
            elif kind == "TabularSection":
                self.count(section=True)
                props = self.single(node, "Properties")
                if props is None:
                    raise CoreError("METADATA_SEARCH_UNSUPPORTED", "Tabular section has no Properties")
                self.text(props, "Name")
                nested = self.single(node, "ChildObjects")
                if nested is not None:
                    for child_index, child in enumerate(nested, 1):
                        self.checkpoint()
                        if _local(child.tag) == "Attribute":
                            field(child, child_index, node, index)
        return matches, total

    def coverage(self, unsupported_roots=0):
        self.checkpoint()
        return {"scope": SCOPE, "fields_scanned": self.fields,
                "tabular_sections_scanned": self.sections,
                "unsupported_metadata_roots": unsupported_roots, "complete": unsupported_roots == 0}
