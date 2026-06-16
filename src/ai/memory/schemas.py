from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import time

class MemorySource(str, Enum):
    """Источник воспоминания для отслеживания происхождения (Provenance)."""
    USER_INPUT = "user_input"   # Прямой ввод пользователя
    INFERENCE = "inference"     # Вывод, сделанный AI в ходе работы
    DREAM = "dream"             # Синтетическое воспоминание из "сна"
    WEB_SEARCH = "web_search"   # Данные из внешнего поиска
    CODE_ANALYSIS = "code_analysis" # Данные из анализа кода

class Provenance(BaseModel):
    """Метаданные происхождения информации."""
    source: MemorySource
    confidence: float = Field(..., ge=0.0, le=1.0, description="Уверенность в достоверности (0.0 - 1.0)")
    timestamp: float = Field(default_factory=time.time, description="Время создания воспоминания")
    author_agent: Optional[str] = Field(None, description="Имя агента, создавшего запись")
    context_id: Optional[str] = Field(None, description="ID сессии или задачи")

class MemoryItem(BaseModel):
    """Единица памяти (Эпизод или Факт)."""
    id: str
    content: str = Field(..., description="Текстовое содержание воспоминания")
    embedding: Optional[List[float]] = Field(None, description="Векторное представление")
    provenance: Provenance
    
    # Ebbinghaus Decay Attributes
    created_at: float = Field(default_factory=time.time)
    last_accessed: float = Field(default_factory=time.time)
    access_count: int = Field(0, description="Сколько раз обращались к этому факту")
    strength: float = Field(1.0, description="Текущая сила воспоминания (с учетом забывания)")

    def update_access(self):
        """Обновить статистику доступа (Spaced Repetition)."""
        self.last_accessed = time.time()
        self.access_count += 1
        # Увеличение силы при повторном доступе (Reinforcement)
        self.strength = min(self.strength + 0.1, 1.5) 

    def calculate_retention(self, current_time: float = None) -> float:
        """
        Рассчитать текущий уровень удержания по кривой Эббингауза.
        R = e^(-t/S)
        где t - время с последнего доступа, S - сила памяти (Stability).
        """
        if current_time is None:
            current_time = time.time()
            
        time_elapsed = current_time - self.last_accessed
        # Stability растет с количеством повторений
        stability = self.strength * (1 + 0.5 * self.access_count)
        
        # Простая модель экспоненциального затухания
        # time_elapsed в часах для удобства масштаба (3600 сек)
        t_hours = time_elapsed / 3600.0
        
        import math
        retention = math.exp(-t_hours / stability)
        return retention
