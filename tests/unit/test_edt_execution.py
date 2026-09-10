"""Faults must retain intent and never silently replay an EDT write."""
import asyncio
import json

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.edt_execution import EDTClient


class Reply:
    isError = False
    structuredContent = {"success": True}

    def model_dump(self, **kwargs):
        return {
            "isError": self.isError,
            "structuredContent": self.structuredContent,
            "content": [],
        }


class Session:
    def __init__(self, behavior):
        self.behavior, self.calls = behavior, []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return await self.behavior()


def test_timeout_retains_intent_blocks_followup_and_does_not_retry(tmp_path):
    async def scenario():
        async def hang():
            assert (tmp_path / "001-request.json").exists()
            await asyncio.sleep(30)

        session = Session(hang)
        client = EDTClient(session, tmp_path, lambda: None, timeout=0.02)
        with pytest.raises(CoreError) as error:
            await client.import_configuration()
        assert error.value.code == "EDT_OUTCOME_UNKNOWN"
        assert (
            json.loads((tmp_path / "001-outcome.json").read_bytes())["status"]
            == "unknown"
        )
        with pytest.raises(CoreError):
            await client.import_configuration()
        assert len(session.calls) == 1

    asyncio.run(scenario())


def test_revoke_during_pending_call_cancels_and_suppresses_result(tmp_path):
    async def scenario():
        revoked = False
        cancelled = False

        def check():
            if revoked:
                raise CoreError("PROJECT_FORBIDDEN", "revoked")

        async def hang():
            nonlocal revoked, cancelled
            revoked = True
            try:
                await asyncio.sleep(30)
            finally:
                cancelled = True

        session = Session(hang)
        client = EDTClient(session, tmp_path, check, timeout=3)
        with pytest.raises(CoreError) as error:
            await client.import_configuration()
        assert error.value.code == "PROJECT_FORBIDDEN"
        assert cancelled
        assert not (tmp_path / "001-response.json").exists()

    asyncio.run(scenario())


def test_rename_is_typed_and_preview_token_is_required(tmp_path):
    async def scenario():
        async def reply():
            return Reply()

        session = Session(reply)
        client = EDTClient(session, tmp_path, lambda: None)
        with pytest.raises(CoreError):
            await client.rename_attribute(
                "Products", "Article", "SKU", expected_hash="bad"
            )
        with pytest.raises(CoreError):
            await client.rename_attribute(
                "../other", "Article", "SKU", expected_hash=None
            )
        assert session.calls == []
        await client.rename_attribute(
            "Products", "Article", "SKU", expected_hash="1234567890abcdef"
        )
        name, args = session.calls[0]
        assert name == "rename_metadata_object"
        assert args == {
            "projectName": "RentgenCandidate",
            "objectFqn": "Catalog.Products.Attribute.Article",
            "newName": "SKU",
            "confirm": True,
            "expectedHash": "1234567890abcdef",
            "timeout": 60,
        }

    asyncio.run(scenario())


def test_structured_failure_is_not_recorded_as_success(tmp_path):
    async def scenario():
        async def reply():
            result = Reply()
            result.structuredContent = {"success": False, "error": "failed"}
            return result

        session = Session(reply)
        client = EDTClient(session, tmp_path, lambda: None)
        with pytest.raises(CoreError):
            await client.import_configuration()
        assert (
            json.loads((tmp_path / "001-outcome.json").read_bytes())["status"]
            == "rejected"
        )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "message, expected",
    [
        (
            "Could not get configuration for project: RentgenCandidate",
            "EDT_MODEL_NOT_READY",
        ),
        ("Access denied", "EDT_MODEL_REJECTED"),
    ],
)
def test_readiness_retries_only_loading_and_obeys_deadline(tmp_path, message, expected):
    async def scenario():
        async def reply():
            result = Reply()
            result.isError = True
            result.structuredContent = {"success": False, "error": message}
            return result

        session = Session(reply)
        client = EDTClient(session, tmp_path, lambda: None)
        with pytest.raises(CoreError) as error:
            await client.wait_for_model("Products", timeout=0.02)
        assert error.value.code == expected
        assert len(session.calls) == 1
        assert session.calls[0][0] == "get_metadata_details"
        with pytest.raises(CoreError):
            await client.import_configuration()
        assert len(session.calls) == 1

    asyncio.run(scenario())


def test_oversized_response_preserves_unresolved_intent(tmp_path):
    async def scenario():
        async def reply():
            result = Reply()
            result.structuredContent = {"text": "x" * (2 * 1024**2)}
            return result

        session = Session(reply)
        client = EDTClient(session, tmp_path, lambda: None)
        with pytest.raises(CoreError) as error:
            await client.import_configuration()
        assert error.value.code == "EDT_OUTPUT_LIMIT"
        assert not (tmp_path / "001-response.json").exists()
        assert (
            json.loads((tmp_path / "001-outcome.json").read_bytes())["status"]
            == "unknown"
        )

    asyncio.run(scenario())
