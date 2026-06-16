import logging
from typing import List, Dict, Optional
import uuid
import time
from src.utils.structured_logging import StructuredLogger
from src.ai.memory.schemas import MemoryItem, Provenance, MemorySource

logger = StructuredLogger(__name__).logger

class Memorizer:
    """
    Cognitive Memory Manager (Memorizer).
    Отвечает за сохранение, извлечение и управление жизненным циклом воспоминаний.
    Реализует кривую забывания Эббингауза.
    """

    def __init__(self, storage_adapter=None):
        """
        Args:
            storage_adapter: Адаптер к БД (Qdrant/Neo4j). Пока используем in-memory dict для прототипа.
        """
        self.storage = storage_adapter if storage_adapter else {} # Mock storage: id -> MemoryItem
        self.logger = logger

    def remember(self, content: str, source: MemorySource, confidence: float = 1.0, metadata: Dict = None) -> str:
        """
        Сохранить новое воспоминание.
        """
        provenance = Provenance(
            source=source,
            confidence=confidence,
            metadata=metadata or {}
        )
        
        item_id = str(uuid.uuid4())
        item = MemoryItem(
            id=item_id,
            content=content,
            provenance=provenance
        )
        
        # В реальной реализации здесь будет вызов Qdrant для получения эмбеддинга и сохранения
        self.storage[item_id] = item
        
        self.logger.info(f"Memorized item {item_id}", extra={
            "content_preview": content[:50],
            "source": source.value,
            "confidence": confidence
        })
        
        return item_id

    def recall(self, query: str = None, min_retention: float = 0.2) -> List[MemoryItem]:
        """
        Извлечь воспоминания.
        Фильтрует "забытые" факты (retention < min_retention).
        """
        current_time = time.time()
        results = []
        
        # В реальной реализации здесь будет семантический поиск (Vector Search)
        # Сейчас просто перебор для демонстрации логики Ebbinghaus
        
        for item in self.storage.values():
            retention = item.calculate_retention(current_time)
            
            if retention >= min_retention:
                # Если мы "вспомнили" это (нашли в поиске), мы обновляем доступ
                # В реальном поиске это должно происходить только для топ-K результатов
                # item.update_access() # Это лучше делать явно при использовании
                results.append(item)
            else:
                self.logger.debug(f"Item {item.id} faded (retention: {retention:.2f})")

        # Сортировка по retention (свежести/силе)
        results.sort(key=lambda x: x.calculate_retention(current_time), reverse=True)
        return results

    def reinforce(self, item_id: str):
        """
        "Подкрепить" воспоминание (Spaced Repetition).
        Вызывается, когда агент использует этот факт.
        """
        if item_id in self.storage:
            item = self.storage[item_id]
            old_strength = item.strength
            item.update_access()
            self.logger.info(f"Reinforced memory {item_id}", extra={
                "old_strength": old_strength,
                "new_strength": item.strength,
                "access_count": item.access_count
            })

    def prune_forgotten(self, threshold: float = 0.1) -> int:
        """
        Удалить воспоминания, которые окончательно забыты.
        """
        current_time = time.time()
        to_remove = []
        
        for item_id, item in self.storage.items():
            if item.calculate_retention(current_time) < threshold:
                to_remove.append(item_id)
        
        for item_id in to_remove:
            del self.storage[item_id]
            
        self.logger.info(f"Pruned {len(to_remove)} forgotten memories")
        return len(to_remove)
