"""Portable source locator validation; never resolves a live filesystem path."""
import unicodedata

from .errors import CoreError
from .source_configuration import _validate_relative_root


def validate_source_path(value: str) -> str:
    try:
        if value == ".":
            raise ValueError
        _validate_relative_root(value)
    except (CoreError, ValueError, TypeError) as exc:
        raise CoreError("SOURCE_PATH_UNSAFE", "Invalid relative source path") from exc
    return value


def collision_key(value: str) -> str:
    return unicodedata.normalize("NFC", validate_source_path(value)).casefold()


def validate_inventory_paths(paths) -> None:
    seen = set()
    for path in paths:
        key = collision_key(path)
        if key in seen:
            raise CoreError("SOURCE_PATH_COLLISION", "Ambiguous source inventory path")
        seen.add(key)


def validate_file_paths(paths):
    """Also reject an inferred directory alias or a file used as a parent."""
    paths = tuple(paths)
    validate_inventory_paths(paths)
    files = {collision_key(path) for path in paths}
    directories = {}
    for path in paths:
        parts = path.split("/")
        for end in range(1, len(parts)):
            directory = "/".join(parts[:end])
            key = collision_key(directory)
            if key in files or (key in directories and directories[key] != directory):
                raise CoreError(
                    "SOURCE_PATH_COLLISION", "Ambiguous source directory path"
                )
            directories[key] = directory
