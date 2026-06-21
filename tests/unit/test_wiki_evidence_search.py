import pytest

from src.services.wiki.search import WikiSearchService
from src.services.wiki.service import WikiService


@pytest.mark.asyncio
async def test_ask_wiki_returns_caveated_no_evidence_answer(monkeypatch):
    service = WikiService()

    async def no_evidence(query: str, limit: int = 5):
        return []

    monkeypatch.setattr(service, "_search_local_pages", no_evidence)

    result = await service.ask_wiki("How does Platform Doctor prove upgrade risk?")

    assert result["coverage"] == "no_local_evidence"
    assert result["sources"] == []
    assert result["evidence"] == []
    assert result["mode"] == "offline-evidence-search"
    assert "stub" not in result["answer"].lower()
    assert "not invent" in result["answer"].lower()
    assert result["caveats"]


@pytest.mark.asyncio
async def test_ask_wiki_returns_sources_from_local_evidence(monkeypatch):
    service = WikiService()

    async def local_evidence(query: str, limit: int = 5):
        return [
            {
                "title": "Platform Doctor",
                "slug": "platform-doctor",
                "namespace": "ops",
                "score": 1.0,
                "snippet": "Platform Doctor maps platform drift to upgrade gates.",
                "source": "/wiki/pages/platform-doctor",
                "updated_at": "2026-06-20T00:00:00",
            }
        ]

    monkeypatch.setattr(service, "_search_local_pages", local_evidence)

    result = await service.ask_wiki("Platform Doctor upgrade gates")

    assert result["coverage"] == "local_wiki_evidence"
    assert result["sources"] == ["/wiki/pages/platform-doctor"]
    assert result["evidence"][0]["title"] == "Platform Doctor"
    assert "Platform Doctor" in result["answer"]
    assert "invented summary" in result["answer"]
    assert "stub" not in result["answer"].lower()


@pytest.mark.asyncio
async def test_wiki_search_offline_index_does_not_return_mock_results():
    service = WikiSearchService()

    index_result = await service.index_page(
        page_id="page-platform",
        title="Platform Doctor",
        content="Platform Doctor checks platform version drift and upgrade readiness.",
    )
    results = await service.search("upgrade platform readiness", limit=3)

    assert index_result["mode"] == "offline-lexical"
    assert results
    assert results[0]["page_id"] == "page-platform"
    assert results[0]["mode"] == "offline-lexical"
    assert "mock-id" not in {item["page_id"] for item in results}
    assert all("High level overview of the system" not in item["snippet"] for item in results)
