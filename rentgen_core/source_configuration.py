"""Versioned registered layer locators, not captured source evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import stat
from typing import TYPE_CHECKING, Literal
import unicodedata

from .errors import CoreError

if TYPE_CHECKING:
    from .context import ProjectContext


def _invalid():
    return CoreError("SOURCE_LAYER_INVALID", "Invalid source layer configuration")


def _validate_relative_root(value):
    if value == ".":
        return
    if not isinstance(value, str) or not value:
        raise _invalid()
    for part in value.split("/"):
        device = part.split(".", 1)[0].upper()
        if (
            not part
            or part in (".", "..")
            or part.endswith((".", " "))
            or any(
                c in '<>:"\\|?*' or ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF
                for c in part
            )
            or device in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
            or re.fullmatch(r"(?:COM|LPT)[1-9¹²³]", device)
        ):
            raise _invalid()


def _revision(value, *, minimum=1):
    if type(value) is not int or not minimum <= value < 2**63:
        raise _invalid()


@dataclass(frozen=True)
class SourceLayerSpec:
    layer_id: str
    ordinal: int
    kind: Literal["base", "extension"]
    root_relative_path: str
    source_format: Literal["designer_xml", "edt", "unknown"]

    def __post_init__(self):
        if (
            not isinstance(self.layer_id, str)
            or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", self.layer_id)
            or self.kind not in ("base", "extension")
            or self.source_format not in ("designer_xml", "edt", "unknown")
        ):
            raise _invalid()
        _revision(self.ordinal, minimum=0)
        _validate_relative_root(self.root_relative_path)


def _validate_layers(layers):
    if not isinstance(layers, tuple) or not layers:
        raise _invalid()
    ids, roots = set(), []
    for ordinal, layer in enumerate(layers):
        if not isinstance(layer, SourceLayerSpec):
            raise _invalid()
        if layer.ordinal != ordinal or layer.kind != (
            "base" if ordinal == 0 else "extension"
        ):
            raise _invalid()
        root = unicodedata.normalize("NFC", layer.root_relative_path).casefold()
        if layer.layer_id in ids or any(
            root == old
            or root == "."
            or old == "."
            or root.startswith(old + "/")
            or old.startswith(root + "/")
            for old in roots
        ):
            raise _invalid()
        ids.add(layer.layer_id)
        roots.append(root)


@dataclass(frozen=True)
class SourceConfiguration:
    revision: int
    layers: tuple[SourceLayerSpec, ...]

    def __post_init__(self):
        _revision(self.revision)
        _validate_layers(self.layers)


def _checked_directory(path):
    """Registration-time checks only; capture must separately hold confined handles."""
    path = Path(path).absolute()
    try:
        for ancestor in (*reversed(path.parents), path):
            info = ancestor.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & 0x400
            ):
                raise CoreError(
                    "SOURCE_PATH_UNSAFE",
                    "Source registration crosses a link or reparse point",
                )
            if not stat.S_ISDIR(info.st_mode):
                raise CoreError(
                    "SOURCE_ROOT_UNAVAILABLE", "Registered root is not a directory"
                )
        return path.resolve(strict=True)
    except OSError as exc:
        raise CoreError(
            "SOURCE_ROOT_UNAVAILABLE", "Registered source directory is unavailable"
        ) from exc


def validate_layer_roots(
    layers: tuple[SourceLayerSpec, ...], source_root: Path, state_root: Path
) -> tuple[tuple[str, str], ...]:
    """Check trusted locators; return exact (layer_id, state-relative-path) exclusions.

    No source bytes are opened. These administrative checks do not implement the
    handle-bound capture reader or protect a later read against filesystem races.
    """
    _validate_layers(layers)
    source = _checked_directory(source_root)
    state = _checked_directory(state_root)
    if source.is_relative_to(state):
        raise _invalid()
    resolved = []
    exclusions = []
    for layer in layers:
        root = _checked_directory(source / layer.root_relative_path)
        if (
            not root.is_relative_to(source)
            or root.is_relative_to(state)
            or any(
                root.is_relative_to(old) or old.is_relative_to(root) for old in resolved
            )
        ):
            raise _invalid()
        resolved.append(root)
        if state.is_relative_to(root):
            exclusions.append((layer.layer_id, state.relative_to(root).as_posix()))
    return tuple(exclusions)


def get_source_configuration(ctx: ProjectContext) -> SourceConfiguration:
    if ctx is None:
        raise CoreError("CONTEXT_REQUIRED", "Project context is required")
    with ctx.state.transaction(ctx.principal) as tx:
        return tx.get_source_configuration()


def configure_source_layers(
    ctx: ProjectContext, layers: tuple[SourceLayerSpec, ...], *, expected_revision: int
) -> SourceConfiguration:
    if ctx is None:
        raise CoreError("CONTEXT_REQUIRED", "Project context is required")
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        return tx.configure_source_layers(
            layers, expected_revision=expected_revision, source_root=ctx.source_root
        )
