"""Bounded search over a verified manifest; never opens live source files."""
import re
import unicodedata

from .errors import CoreError


def source_query(*, query="", kind="all", layer=None):
    if (
        not isinstance(query, str)
        or len(query) > 256
        or any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in query)
        or len(query.encode("utf-8")) > 1024
        or not isinstance(kind, str)
        or kind not in {"all", "module"}
        or layer is not None
        and (
            not isinstance(layer, str)
            or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", layer)
        )
    ):
        raise CoreError("INVALID_QUERY_OPTIONS", "Invalid source discovery filters")
    return {"query": query, "kind": kind, "layer": layer}


def selected_entries(document, options):
    entries = document["source"]["entries"]
    layer = options["layer"]
    if layer is not None and not any(
        item["layer_id"] == layer for item in document["source"]["layers"]
    ):
        raise CoreError(
            "INVALID_QUERY_OPTIONS", "Source layer is absent from this snapshot"
        )
    if options == {"query": "", "kind": "all", "layer": None}:
        return entries
    needle = options["query"].casefold()
    return [
        entry
        for entry in entries
        if (layer is None or entry["layer_id"] == layer)
        and (
            options["kind"] == "all"
            or entry["relative_path"].lower().endswith((".bsl", ".os"))
        )
        and needle in entry["relative_path"].casefold()
    ]
