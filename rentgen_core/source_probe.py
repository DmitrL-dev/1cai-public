"""Read-only live-source digest using the same confined passes as capture."""
from .capture import _inventory, _pass, _reader_factory
from .errors import CoreError
from .manifests import build_source_document, sha256


def probe_sources(ctx):
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all({"project:read", "analysis:run"})
        head, configuration = tx.get_project_head(), tx.get_source_configuration()
    try:
        with _reader_factory(ctx.source_root, ctx.state.path.parent) as reader:
            exclusions = reader.configure(configuration)
            first = _inventory(reader, configuration, exclusions)
            entries = _pass(reader, first)
            second = _inventory(reader, configuration, exclusions)
            if second != first or _pass(reader, second) != entries:
                raise CoreError(
                    "SOURCE_CAPTURE_CHANGED", "Sources changed during probe"
                )
            if _inventory(reader, configuration, exclusions) != second:
                raise CoreError(
                    "SOURCE_CAPTURE_CHANGED", "Inventory changed during probe"
                )
        digest = sha256(
            build_source_document(ctx.project_id, configuration, exclusions, entries)
        )
    except OSError as exc:
        raise CoreError("SOURCE_ROOT_UNAVAILABLE", "Source probe failed") from exc
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all({"project:read", "analysis:run"})
        if tx.get_source_configuration() != configuration:
            raise CoreError(
                "SOURCE_CONFIGURATION_CONFLICT", "Layers changed during probe"
            )
        if tx.get_project_head() != head:
            raise CoreError("HEAD_CONFLICT", "Head changed during probe")
    return head, digest
