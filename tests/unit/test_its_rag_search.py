import pytest

from src.services.its_rag.chunker import ITSChunker
from src.services.its_rag.search import ITSSearchService


@pytest.mark.asyncio
async def test_its_search_offline_uses_local_text_files(tmp_path):
    docs_dir = tmp_path / "sections"
    docs_dir.mkdir()
    (docs_dir / "forms.txt").write_text(
        "7.3.1 Динамический список\n\n"
        "Динамический список получает данные формы и поддерживает поиск.",
        encoding="utf-8",
    )
    (docs_dir / "commands.txt").write_text(
        "7.4 Команды формы\n\n"
        "Команды формы размещаются в командной панели.",
        encoding="utf-8",
    )

    chunker = ITSChunker(docs_dir=str(docs_dir), manifest_path=str(tmp_path / "manifest.json"))
    service = ITSSearchService(mode="offline", chunker=chunker)

    results = await service.query("динамический список поиск", limit=2)

    assert results
    assert results[0].source_file == "forms.txt"
    assert results[0].score > 0

