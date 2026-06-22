from src.ai.memory.consolidator import Consolidator
from src.ai.memory.memory_manager import Memorizer
from src.ai.memory.schemas import MemorySource


def test_consolidator_does_not_create_synthetic_memory_without_llm():
    memorizer = Memorizer()
    memorizer.remember("Fact one", MemorySource.USER_INPUT)
    memorizer.remember("Fact two", MemorySource.CODE_ANALYSIS)

    Consolidator(memorizer).run_maintenance()

    assert all(
        item.provenance.source != MemorySource.DREAM
        for item in memorizer.storage.values()
    )


def test_consolidator_stores_llm_generated_insight_when_configured():
    class LocalLLM:
        def generate(self, prompt):
            return "Observed repeated integration risk."

    memorizer = Memorizer()
    memorizer.remember("Fact one", MemorySource.USER_INPUT)
    memorizer.remember("Fact two", MemorySource.CODE_ANALYSIS)

    Consolidator(memorizer, llm_service=LocalLLM()).run_maintenance()

    dreams = [
        item
        for item in memorizer.storage.values()
        if item.provenance.source == MemorySource.DREAM
    ]
    assert len(dreams) == 1
    assert dreams[0].content == "Observed repeated integration risk."
