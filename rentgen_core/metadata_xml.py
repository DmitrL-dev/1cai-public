"""Bounded XML from verified bytes, without a filename or external resolver."""

import xml.etree.ElementTree as ET

from .errors import CoreError


class _BoundedTree(ET.TreeBuilder):
    def __init__(self, max_nodes, max_depth):
        super().__init__()
        self.nodes = self.depth = 0
        self.max_nodes, self.max_depth = max_nodes, max_depth

    def start(self, tag, attrs):
        self.nodes += 1
        self.depth += 1
        if self.nodes > self.max_nodes or self.depth > self.max_depth:
            raise CoreError("METADATA_LIMIT_EXCEEDED", "XML node/depth limit exceeded")
        return super().start(tag, attrs)

    def end(self, tag):
        result = super().end(tag)
        self.depth -= 1
        return result

    def doctype(self, name, pubid, system):
        # Expat decodes supported XML encodings before invoking this callback.
        # Reject before the internal subset is processed, not with a byte regex.
        raise CoreError(
            "XML_FORBIDDEN", "XML document types and entities are forbidden"
        )


def parse_xml(raw, *, max_bytes=4 * 1024 * 1024, max_nodes=50_000, max_depth=64):
    """Parse raw XML with its own encoding declaration; never recover invalid data."""
    for value, maximum in (
        (max_bytes, 4 * 1024 * 1024),
        (max_nodes, 50_000),
        (max_depth, 64),
    ):
        if type(value) is not int or not 1 <= value <= maximum:
            raise CoreError(
                "INVALID_QUERY_OPTIONS", "XML limits must be positive and bounded"
            )
    if not isinstance(raw, bytes):
        raise CoreError("XML_INVALID", "XML requires verified raw bytes")
    if len(raw) > max_bytes:
        raise CoreError("METADATA_LIMIT_EXCEEDED", "XML byte limit exceeded")
    try:
        parser = ET.XMLParser(target=_BoundedTree(max_nodes, max_depth))
        parser.feed(raw)
        return parser.close()
    except (ET.ParseError, ValueError, LookupError) as error:
        raise CoreError(
            "XML_INVALID", "Malformed or unsupported XML encoding"
        ) from error
