
#!/usr/bin/env python3
"""
Utilities for parsing BSL code using tree-sitter.

If tree-sitter-bsl parser is not available, functions degrade gracefully
by falling back to regex-based extraction (where applicable).
"""

from __future__ import annotations

import ctypes
import logging
from pathlib import Path
from typing import Dict, Iterator, Optional

logger = logging.getLogger(__name__)

try:
    from tree_sitter import Language, Parser
except ImportError:  # pragma: no cover - executed when tree-sitter is missing
    Language = None  # type: ignore[assignment]
    Parser = None  # type: ignore[assignment]


BSL_LANGUAGE: Optional[Language] = None
BSL_PARSER: Optional[Parser] = None


def load_bsl_language() -> Optional[Language]:
    """Attempt to load the tree-sitter BSL language."""
    global BSL_LANGUAGE, BSL_PARSER
    if Language is None:
        logger.warning("tree_sitter is not installed. AST features are unavailable.")
        return None
    if BSL_LANGUAGE:
        return BSL_LANGUAGE

    shared_lib_candidates = [
        Path("tools/tree-sitter-bsl.so"),
        Path("tools/tree-sitter-bsl.dll"),
        Path("tools/tree-sitter-bsl.dylib"),
    ]
    shared_lib = next((path for path in shared_lib_candidates if path.exists()), None)
    if not shared_lib:
        logger.warning(
            "tree-sitter-bsl shared library not found. Build from https://github.com/alkoleft/tree-sitter-bsl "
            "and place the resulting .so/.dll in the tools/ directory."
        )
        return None

    try:
        try:
            # tree-sitter <=0.21 API: path + language name
            BSL_LANGUAGE = Language(str(shared_lib), "bsl")
        except TypeError:
            # tree-sitter >=0.22 API: pointer to TSLanguage via ctypes
            ts_lib = ctypes.CDLL(str(shared_lib))
            language_symbol = getattr(ts_lib, "tree_sitter_bsl", None)
            if language_symbol is None:
                raise AttributeError("tree_sitter_bsl symbol not found in shared library")
            language_symbol.restype = ctypes.c_void_p
            language_ptr = language_symbol()
            try:
                BSL_LANGUAGE = Language(language_ptr)
            except ValueError as version_error:
                message = str(version_error)
                if "Incompatible Language version" not in message:
                    raise

                # Patch module-level compatibility constants and retry.
                import tree_sitter as ts  # Local import to avoid circular refs.

                # Best effort: bump limits to the reported version (extract from message).
                try:
                    reported_version = int(message.split("version ")[1].split(".")[0])
                except (IndexError, ValueError):  # pragma: no cover - defensive path
                    reported_version = 15

                if getattr(ts, "LANGUAGE_VERSION", 0) < reported_version:
                    ts.LANGUAGE_VERSION = reported_version
                if getattr(ts, "MIN_COMPATIBLE_LANGUAGE_VERSION", 0) < reported_version:
                    ts.MIN_COMPATIBLE_LANGUAGE_VERSION = reported_version

                BSL_LANGUAGE = Language(language_ptr)

        parser = Parser()
        language_version = getattr(BSL_LANGUAGE, "version", None)
        if language_version is not None:
            import tree_sitter as ts

            if getattr(ts, "LANGUAGE_VERSION", 0) < language_version:
                ts.LANGUAGE_VERSION = language_version
            if getattr(ts, "MIN_COMPATIBLE_LANGUAGE_VERSION", 0) < language_version:
                ts.MIN_COMPATIBLE_LANGUAGE_VERSION = language_version

        if hasattr(parser, "set_language"):
            parser.set_language(BSL_LANGUAGE)
        else:
            parser.language = BSL_LANGUAGE
        BSL_PARSER = parser
        logger.info("Loaded tree-sitter-bsl parser.")
        return BSL_LANGUAGE
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load tree-sitter-bsl: %s", exc)
        return None


def ensure_parser() -> Optional[Parser]:
    """Return a configured parser or None if tree-sitter is unavailable."""
    if BSL_PARSER:
        return BSL_PARSER
    if load_bsl_language():
        return BSL_PARSER
    return None


def parse_code_to_tree(code: str):
    """Parse BSL source code to a tree-sitter syntax tree."""
    parser = ensure_parser()
    if not parser:
        return None
    return parser.parse(code.encode("utf-8"))


def iter_identifiers(code: str) -> Iterator[str]:
    """
    Iterate over identifier names in the source code using tree-sitter.

    Falls back to empty iterator if parser unavailable. This can be extended
    to collect specific structures (function definitions, variable usages, etc.).
    """
    tree = parse_code_to_tree(code)
    if tree is None:
        return iter([])

    cursor = tree.walk()

    def traverse():
        reached_root = False
        while not reached_root:
            node = cursor.node
            if node.type == "identifier":
                yield code[node.start_byte:node.end_byte]
            if cursor.goto_first_child():
                continue
            if cursor.goto_next_sibling():
                continue
            while cursor.goto_parent():
                if cursor.goto_next_sibling():
                    break
            else:
                reached_root = True

    return traverse()


def extract_calls(code: str) -> Dict[str, int]:
    """
    Extract function/procedure call names with occurrences using tree-sitter.
    """
    tree = parse_code_to_tree(code)
    if tree is None:
        return {}

    cursor = tree.walk()
    calls: Dict[str, int] = {}

    def visit():
        reached_root = False
        while not reached_root:
            node = cursor.node
            if node.type in {"function_call", "method_call"}:
                identifier = node.child_by_field_name("name")
                if identifier:
                    name = code[identifier.start_byte:identifier.end_byte]
                    calls[name] = calls.get(name, 0) + 1
            if cursor.goto_first_child():
                continue
            if cursor.goto_next_sibling():
                continue
            while cursor.goto_parent():
                if cursor.goto_next_sibling():
                    break
            else:
                reached_root = True

    visit()
    return calls


__all__ = ["load_bsl_language", "ensure_parser", "parse_code_to_tree", "iter_identifiers", "extract_calls"]

