"""Versioned source keys; these are path identities, never 1C metadata UUIDs.

Project/generation is the enclosing store. Every directory (including extension
layers, metadata types, forms and commands) participates in identity. Original
spelling is retained separately; SQLite NOCASE is not Unicode-aware.
"""

import unicodedata
from pathlib import PurePosixPath

IDENTITY_VERSION = "source-path-v1"
SCHEMA_VERSION = "2"

_RUNTIME_TYPES = {
    "commonmodule": "commonmodules",
    "commonmodules": "commonmodules",
    "общиймодуль": "commonmodules",
    "document": "documents",
    "documents": "documents",
    "документ": "documents",
    "catalog": "catalogs",
    "catalogs": "catalogs",
    "справочник": "catalogs",
}
_RUNTIME_KINDS = {
    "module": "module",
    "модуль": "module",
    "objectmodule": "objectmodule",
    "модульобъекта": "objectmodule",
    "managermodule": "managermodule",
    "модульменеджера": "managermodule",
}


def identifier_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def source_key(path: str) -> str:
    path = path.replace("\\", "/")
    parts = path.split("/")
    if (
        not path
        or path.startswith("/")
        or any(p in {"", ".", ".."} or ":" in p for p in parts)
    ):
        raise ValueError(
            f"source_path must be a root-relative file path without traversal: {path!r}"
        )
    return identifier_key(path)


def runtime_source_tail(reference: str) -> str | None:
    """Bounded TJ adapter, not BSL expression/type resolution.

    Recognize exactly Type.Owner.Kind for common modules, documents and
    catalogs. The full typed source tail is matched at a directory boundary;
    layer prefixes are retained as distinct candidates by the store. Nested
    forms/commands and unsupported metadata types must supply their source path.
    """
    parts = reference.split(".")
    if len(parts) != 3 or not all(p.isidentifier() for p in parts):
        return None
    metadata_type = _RUNTIME_TYPES.get(identifier_key(parts[0]))
    kind = _RUNTIME_KINDS.get(identifier_key(parts[2]))
    if metadata_type is None or kind is None:
        return None
    if (metadata_type == "commonmodules") != (kind == "module"):
        return None
    return f"{metadata_type}/{identifier_key(parts[1])}/ext/{kind}.bsl"


def module_identity(record: dict) -> tuple[str, str | None, str]:
    path = record.get("source_path")
    if path:
        return "source:" + source_key(path), path, "source_path"
    alias = record["module"]
    # Old common modules have a single lexical alias. Forms, commands and other
    # metadata owners lost necessary path segments and cannot be reconstructed.
    if not alias.isidentifier():
        raise ValueError(
            f"ambiguous legacy module {alias!r}: source_path is required; rescan with the current scanner"
        )
    return "legacy:" + identifier_key(alias), None, "legacy_alias"


def source_metadata(path: str | None, display_name: str) -> tuple[str, str, str | None]:
    """Return presentation owner/kind and a bounded common-module receiver key.

    Only the exact CommonModules/<name>/Ext/Module.bsl tail is recognized as a
    common module. No manager/object receiver mapping or type inference exists.
    """
    if path is None:
        return display_name, "module", identifier_key(display_name)
    parts = path.replace("\\", "/").split("/")
    keys = [identifier_key(p) for p in parts]
    if (
        len(parts) >= 4
        and keys[-4] == "commonmodules"
        and keys[-2:] == ["ext", "module.bsl"]
    ):
        return parts[-3], "module", keys[-3]
    kind = identifier_key(PurePosixPath(path.replace("\\", "/")).stem)
    if "forms" in keys or keys[-2:] == ["form", "module.bsl"]:
        kind = "form"
    owner = display_name.split(".", 1)[0]
    for segment in ("forms", "commands", "ext"):
        if segment in keys and keys.index(segment) > 0:
            owner = parts[keys.index(segment) - 1]
            break
    return owner, kind, None
