"""Typed EDT calls with durable intent and no automatic retry of writes."""
import asyncio
import os
import re
import time

from .errors import CoreError
from .manifests import canonical_bytes

PROJECT = "RentgenCandidate"
IDENTIFIER = re.compile(r"[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё_0-9]{0,79}")
MIN_RETRY_WINDOW = 0.05


def write_record(path, value):
    raw = canonical_bytes(value)
    if len(raw) > 2 * 1024**2:
        raise CoreError("EDT_OUTPUT_LIMIT", "EDT record exceeds 2 MiB")
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


async def guarded_wait(awaitable, check, timeout):
    task = asyncio.ensure_future(awaitable)
    deadline = time.monotonic() + timeout
    try:
        while True:
            check()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("EDT response deadline exceeded")
            done, _ = await asyncio.wait({task}, timeout=min(0.25, remaining))
            check()
            if done:
                return task.result()
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def rejected(result):
    return result.isError or (
        isinstance(result.structuredContent, dict)
        and result.structuredContent.get("success") is False
    )


class EDTClient:
    """Internal executor API; transport, paths and project are never model inputs."""

    def __init__(self, session, run, check, *, timeout=90):
        self.session, self.run, self.check = session, run, check
        self.timeout, self.sequence, self.failed = timeout, 0, False

    async def _call(self, name, arguments, *, readiness=False, timeout=None):
        self.check()
        if self.failed:
            raise CoreError(
                "EDT_RECONCILIATION_REQUIRED", "Session has an unresolved call"
            )
        if self.sequence >= 128:
            raise CoreError("EDT_CALL_LIMIT", "EDT session call limit exceeded")
        self.sequence += 1
        prefix = f"{self.sequence:03d}"
        write_record(
            self.run / (prefix + "-request.json"),
            {"tool": name, "arguments": arguments},
        )
        try:
            result = await guarded_wait(
                self.session.call_tool(name, arguments),
                self.check,
                self.timeout if timeout is None else min(self.timeout, timeout),
            )
            write_record(
                self.run / (prefix + "-response.json"), result.model_dump(mode="json")
            )
            bad = rejected(result)
            write_record(
                self.run / (prefix + "-outcome.json"),
                {"status": "rejected" if bad else "response_received"},
            )
        except BaseException as exc:
            self.failed = True
            outcome = self.run / (prefix + "-outcome.json")
            if not outcome.exists():
                write_record(outcome, {"status": "unknown"})
            self.check()
            if isinstance(exc, (CoreError, asyncio.CancelledError, KeyboardInterrupt)):
                raise
            raise CoreError(
                "EDT_OUTCOME_UNKNOWN",
                "EDT call did not produce a confirmed response; do not replay writes",
            ) from exc
        if bad and not readiness:
            self.failed = True
            raise CoreError(
                "EDT_CALL_REJECTED", "EDT rejected the call; inspect retained evidence"
            )
        self.check()
        return result

    async def import_configuration(self):
        return await self._call(
            "import_configuration_from_xml",
            {"projectName": PROJECT, "importPath": str(self.run / "input")},
        )

    async def export_configuration(self, phase):
        if phase not in {"baseline", "candidate"}:
            raise CoreError("EDT_INPUT_INVALID", "Unknown export phase")
        return await self._call(
            "export_configuration_to_xml",
            {"projectName": PROJECT, "outputPath": str(self.run / (phase + "-xml"))},
        )

    async def wait_for_model(self, catalog, *, timeout=90):
        if not (type(catalog) is str and IDENTIFIER.fullmatch(catalog)):
            raise CoreError("EDT_INPUT_INVALID", "Unsupported catalog identifier")
        deadline = time.monotonic() + timeout
        for attempt in range(46):
            remaining = deadline - time.monotonic()
            # A readiness probe performs filesystem journaling around each
            # request. Do not begin another probe when less than one scheduler
            # quantum remains; it cannot complete reliably before the caller's
            # deadline and makes short timeouts nondeterministic.
            if attempt and remaining <= MIN_RETRY_WINDOW:
                break
            result = await self._call(
                "get_metadata_details",
                {
                    "projectName": PROJECT,
                    "objectFqns": ["Catalog." + catalog],
                    "full": True,
                },
                readiness=True,
                timeout=remaining,
            )
            if not rejected(result):
                return result
            content = result.structuredContent
            message = content.get("error", "") if isinstance(content, dict) else ""
            if not isinstance(message, str) or not message.startswith(
                "Could not get configuration for project: " + PROJECT
            ):
                self.failed = True
                raise CoreError("EDT_MODEL_REJECTED", "EDT model read failed")
            if time.monotonic() >= deadline:
                break
            # Sleep a small margin past the deadline so a scheduler wake-up that
            # lands just before it cannot start another request with only a few
            # microseconds left. The next loop iteration still performs the
            # authoritative monotonic deadline check.
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            await guarded_wait(asyncio.sleep(min(2, remaining) + 0.001), self.check, 3)
        self.failed = True
        raise CoreError("EDT_MODEL_NOT_READY", "EDT model did not become ready")

    async def rename_attribute(
        self, catalog, attribute, new_name, *, expected_hash=None
    ):
        if not all(
            type(value) is str and IDENTIFIER.fullmatch(value)
            for value in (catalog, attribute, new_name)
        ):
            raise CoreError("EDT_INPUT_INVALID", "Unsupported metadata identifier")
        if expected_hash is not None and not (
            type(expected_hash) is str and re.fullmatch(r"[0-9a-f]{16}", expected_hash)
        ):
            raise CoreError("EDT_INPUT_INVALID", "Expected rename preview hash")
        arguments = {
            "projectName": PROJECT,
            "objectFqn": f"Catalog.{catalog}.Attribute.{attribute}",
            "newName": new_name,
            "confirm": expected_hash is not None,
            "timeout": 60,
        }
        if expected_hash is not None:
            arguments["expectedHash"] = expected_hash
        return await self._call("rename_metadata_object", arguments)
