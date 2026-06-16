import logging
import time
import random
from typing import List
from src.utils.structured_logging import StructuredLogger
from src.ai.memory.memory_manager import Memorizer
from src.ai.memory.schemas import MemorySource

logger = StructuredLogger(__name__).logger

class Consolidator:
    """
    Отвечает за консолидацию памяти ("Сон").
    Запускает процессы забывания (Pruning) и генерации синтетического опыта (Dreaming).
    """

    def __init__(self, memorizer: Memorizer, llm_service=None):
        self.memorizer = memorizer
        self.llm_service = llm_service # Для генерации снов
        self.logger = logger

    def run_maintenance(self):
        """
        Запустить цикл обслуживания памяти.
        """
        self.logger.info("Starting memory consolidation cycle...")
        
        # 1. Pruning (Забывание)
        pruned_count = self.memorizer.prune_forgotten(threshold=0.1)
        
        # 2. Dreaming (Сны)
        # В реальной системе это должно запускаться, когда нагрузка низкая
        self._dream()
        
        self.logger.info(f"Consolidation complete. Pruned: {pruned_count}")

    def _dream(self):
        """
        Генерация синтетических воспоминаний.
        Берет случайные недавние факты и пытается найти связи или обобщить их.
        """
        # Получаем "активные" воспоминания (те, что еще не забыты)
        active_memories = self.memorizer.recall(min_retention=0.5)
        
        if len(active_memories) < 2:
            return

        # Выбираем пару случайных воспоминаний для синтеза
        # В будущем здесь будет умная логика выбора (Clustering)
        sample = random.sample(active_memories, min(3, len(active_memories)))
        
        context_str = "\n".join([f"- {m.content}" for m in sample])
        
        # Эмуляция генерации инсайта (здесь должен быть вызов LLM)
        # prompt = f"Analyze these facts and generate a generalized insight:\n{context_str}"
        # insight = await self.llm_service.generate(prompt)
        
        # Mock insight
        insight = f"Synthetic insight based on {len(sample)} facts. Pattern detected in user behavior."
        
        # Сохраняем инсайт как новое воспоминание с типом DREAM
        self.memorizer.remember(
            content=insight,
            source=MemorySource.DREAM,
            confidence=0.8,
            metadata={"based_on": [m.id for m in sample]}
        )
        
        self.logger.info("Dream cycle produced new insight", extra={"insight": insight})
