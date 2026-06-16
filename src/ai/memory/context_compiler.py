from typing import List, Dict, Any
from src.utils.structured_logging import StructuredLogger
from src.ai.memory.memory_manager import Memorizer
from src.ai.memory.schemas import MemoryItem

logger = StructuredLogger(__name__).logger

class ContextCompiler:
    """
    Just-in-Time (JIT) Context Compiler.
    Собирает контекст из памяти и формирует структурированный брифинг для LLM.
    """

    def __init__(self, memorizer: Memorizer):
        self.memorizer = memorizer
        self.logger = logger

    def compile_briefing(self, query: str, max_items: int = 5) -> str:
        """
        Собрать брифинг для текущего запроса.
        
        1. Поиск релевантных фактов в памяти.
        2. Ранжирование по релевантности и "силе" памяти.
        3. Форматирование в текст.
        """
        # 1. Recall (в реальной системе query используется для векторного поиска)
        memories = self.memorizer.recall(query=query, min_retention=0.2)
        
        # 2. Ranking (сейчас просто берем топ по retention, который возвращает recall)
        # В будущем: Hybrid Score = Vector Similarity * Retention
        top_memories = memories[:max_items]
        
        if not top_memories:
            return "No relevant context found in memory."

        # 3. Formatting
        briefing_lines = ["## Context Briefing (JIT Compiled)"]
        
        for m in top_memories:
            # Подкрепляем память, так как она пригодилась
            self.memorizer.reinforce(m.id)
            
            source_tag = f"[{m.provenance.source.value.upper()}]"
            confidence = f"{m.provenance.confidence:.2f}"
            briefing_lines.append(f"- {source_tag} (Conf: {confidence}): {m.content}")
            
        return "\n".join(briefing_lines)
