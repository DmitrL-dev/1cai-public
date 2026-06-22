"""
Сборщик метрик эффективности AI-ассистентов.
Отслеживает качество анализа требований, генерации диаграмм и оценки рисков.
"""

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy import JSON, Column, DateTime, Float, String, create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

# SQLAlchemy модели для хранения метрик
Base = declarative_base()


class MetricType(Enum):
    """Типы метрик эффективности"""

    REQUIREMENT_ANALYSIS_ACCURACY = "requirement_analysis_accuracy"
    DIAGRAM_QUALITY_SCORE = "diagram_quality_score"
    RISK_ASSESSMENT_PRECISION = "risk_assessment_precision"
    RECOMMENDATION_QUALITY = "recommendation_quality"
    RESPONSE_TIME = "response_time"
    USER_SATISFACTION = "user_satisfaction"


class AssistantRole(Enum):
    """Роли AI-ассистентов"""

    ARCHITECT = "architect"
    DEVELOPER = "developer"
    TESTER = "tester"
    PM = "product_manager"


@dataclass
class MetricRecord:
    """Запись о метрике"""

    metric_type: MetricType
    assistant_role: AssistantRole
    value: float
    timestamp: datetime
    project_id: str
    user_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    feedback_score: Optional[float] = None


class MetricEvent(Base):
    """Модель события метрики в БД"""

    __tablename__ = "metric_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_type = Column(String, nullable=False)
    assistant_role = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    project_id = Column(String, nullable=False)
    user_id = Column(String)
    context = Column(JSON)
    feedback_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class MetricsDatabase:
    """БД для хранения метрик"""

    def __init__(self):
        self.engine = create_engine(settings.DATABASE_URL)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        Base.metadata.create_all(bind=self.engine)

    def save_metric(self, record: MetricRecord) -> str:
        """Сохранение метрики в БД"""
        session = self.SessionLocal()
        try:
            event = MetricEvent(
                metric_type=record.metric_type.value,
                assistant_role=record.assistant_role.value,
                value=record.value,
                timestamp=record.timestamp,
                project_id=record.project_id,
                user_id=record.user_id,
                context=record.context,
                feedback_score=record.feedback_score,
            )
            session.add(event)
            session.commit()
            logger.info(
                "Сохранена метрика",
                extra={"metric_type": record.metric_type.value, "value": record.value},
            )
            return str(event.id)
        except Exception as e:
            logger.error(
                "Ошибка сохранения метрики",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "metric_type": (
                        record.metric_type.value
                        if hasattr(record, "metric_type")
                        else None
                    ),
                },
                exc_info=True,
            )
            session.rollback()
            raise
        finally:
            session.close()

    def get_metrics(
        self,
        metric_type: MetricType,
        assistant_role: AssistantRole,
        hours_back: int = 24,
        project_id: Optional[str] = None,
    ) -> List[Dict]:
        """Получение метрик за период"""
        session = self.SessionLocal()
        try:
            query = session.query(MetricEvent).filter(
                MetricEvent.metric_type == metric_type.value,
                MetricEvent.assistant_role == assistant_role.value,
                MetricEvent.timestamp
                >= datetime.utcnow() - timedelta(hours=hours_back),
            )

            if project_id:
                query = query.filter(MetricEvent.project_id == project_id)

            events = query.order_by(MetricEvent.timestamp.desc()).all()

            return [asdict(event) for event in events]
        finally:
            session.close()

    def get_aggregated_metrics(
        self, metric_type: MetricType, hours_back: int = 24
    ) -> Dict[str, float]:
        """Агрегированные метрики за период"""
        events = self.get_metrics(metric_type, None, hours_back)

        if not events:
            return {}

        values = [event["value"] for event in events]

        return {
            "mean": np.mean(values),
            "median": np.median(values),
            "std": np.std(values),
            "min": np.min(values),
            "max": np.max(values),
            "count": len(values),
        }


class MetricsCollector:
    """Основной сборщик метрик эффективности"""

    def __init__(self):
        self.db = MetricsDatabase()
        self.logger = logging.getLogger(f"{__name__}.MetricsCollector")

    async def record_requirement_analysis_accuracy(
        self,
        assistant_role: AssistantRole,
        predicted_requirements: List[Dict],
        actual_requirements: List[Dict],
        project_id: str,
        context: Optional[Dict] = None,
    ) -> str:
        """Запись точности анализа требований"""

        # Расчет точности анализа
        accuracy = self._calculate_requirements_accuracy(
            predicted_requirements, actual_requirements
        )

        record = MetricRecord(
            metric_type=MetricType.REQUIREMENT_ANALYSIS_ACCURACY,
            assistant_role=assistant_role,
            value=accuracy,
            timestamp=datetime.utcnow(),
            project_id=project_id,
            context=context,
        )

        metric_id = self.db.save_metric(record)
        self.logger.info(
            f"Сохранена точность анализа требований для {assistant_role.value}: {accuracy:.3f}"
        )
        return metric_id

    async def record_diagram_quality_score(
        self,
        assistant_role: AssistantRole,
        generated_diagram: str,
        user_feedback: Optional[float] = None,
        project_id: str = "",
        context: Optional[Dict] = None,
    ) -> str:
        """Запись качества диаграммы"""

        # Расчет качества диаграммы
        quality_score = self._calculate_diagram_quality(generated_diagram)

        record = MetricRecord(
            metric_type=MetricType.DIAGRAM_QUALITY_SCORE,
            assistant_role=assistant_role,
            value=quality_score,
            timestamp=datetime.utcnow(),
            project_id=project_id,
            context=context,
            feedback_score=user_feedback,
        )

        metric_id = self.db.save_metric(record)
        self.logger.info(
            f"Сохранено качество диаграммы для {assistant_role.value}: {quality_score:.3f}"
        )
        return metric_id

    async def record_risk_assessment_precision(
        self,
        assistant_role: AssistantRole,
        predicted_risks: List[Dict],
        actual_risks: List[Dict],
        project_id: str,
        context: Optional[Dict] = None,
    ) -> str:
        """Запись точности оценки рисков"""

        precision = self._calculate_risk_precision(predicted_risks, actual_risks)

        record = MetricRecord(
            metric_type=MetricType.RISK_ASSESSMENT_PRECISION,
            assistant_role=assistant_role,
            value=precision,
            timestamp=datetime.utcnow(),
            project_id=project_id,
            context=context,
        )

        metric_id = self.db.save_metric(record)
        self.logger.info(
            f"Сохранена точность оценки рисков для {assistant_role.value}: {precision:.3f}"
        )
        return metric_id

    async def record_response_time(
        self,
        assistant_role: AssistantRole,
        response_time: float,
        project_id: str,
        context: Optional[Dict] = None,
    ) -> str:
        """Запись времени ответа"""

        record = MetricRecord(
            metric_type=MetricType.RESPONSE_TIME,
            assistant_role=assistant_role,
            value=response_time,
            timestamp=datetime.utcnow(),
            project_id=project_id,
            context=context,
        )

        metric_id = self.db.save_metric(record)
        self.logger.info(
            f"Сохранено время ответа для {assistant_role.value}: {response_time:.3f}с"
        )
        return metric_id

    async def record_user_satisfaction(
        self,
        assistant_role: AssistantRole,
        satisfaction_score: float,
        project_id: str,
        user_id: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> str:
        """Запись удовлетворенности пользователя"""

        record = MetricRecord(
            metric_type=MetricType.USER_SATISFACTION,
            assistant_role=assistant_role,
            value=satisfaction_score,
            timestamp=datetime.utcnow(),
            project_id=project_id,
            user_id=user_id,
            context=context,
        )

        metric_id = self.db.save_metric(record)
        self.logger.info(
            f"Сохранена удовлетворенность для {assistant_role.value}: {satisfaction_score:.3f}"
        )
        return metric_id

    def _calculate_requirements_accuracy(
        self, predicted: List[Dict], actual: List[Dict]
    ) -> float:
        """Расчет точности анализа требований"""

        if not predicted or not actual:
            return 0.0

        # Преобразуем в множества для сравнения
        predicted_texts = {item.get("text", "").lower().strip() for item in predicted}
        actual_texts = {item.get("text", "").lower().strip() for item in actual}

        # Пересечение и объединение
        intersection = predicted_texts & actual_texts
        union = predicted_texts | actual_texts

        # Jaccard Similarity
        accuracy = len(intersection) / len(union) if union else 0.0

        return min(accuracy, 1.0)

    def _calculate_diagram_quality(self, diagram: str) -> float:
        """Расчет качества диаграммы"""

        if not diagram:
            return 0.0

        # Базовая оценка качества диаграммы
        quality_factors = []

        # Проверка наличия базовых элементов Mermaid
        mermaid_keywords = ["graph", "flowchart", "sequenceDiagram", "classDiagram"]
        keyword_score = sum(
            1 for keyword in mermaid_keywords if keyword in diagram.lower()
        )
        quality_factors.append(keyword_score / len(mermaid_keywords))

        # Проверка наличия узлов и связей
        node_score = 1.0 if diagram.count("-->") > 0 or diagram.count("->") > 0 else 0.0
        quality_factors.append(node_score)

        # Проверка корректной структуры
        structure_score = 1.0 if diagram.count("{") == diagram.count("}") else 0.0
        quality_factors.append(structure_score)

        return np.mean(quality_factors)

    def _calculate_risk_precision(
        self, predicted_risks: List[Dict], actual_risks: List[Dict]
    ) -> float:
        """Расчет точности оценки рисков"""

        if not predicted_risks or not actual_risks:
            return 0.0

        # Извлекаем описания рисков
        predicted_descriptions = {
            risk.get("description", "").lower().strip() for risk in predicted_risks
        }
        actual_descriptions = {
            risk.get("description", "").lower().strip() for risk in actual_risks
        }

        # Пересечение и точность
        intersection = predicted_descriptions & actual_descriptions

        precision = (
            len(intersection) / len(predicted_descriptions)
            if predicted_descriptions
            else 0.0
        )

        return min(precision, 1.0)

    async def get_performance_summary(
        self, hours_back: int = 24
    ) -> Dict[str, Dict[str, float]]:
        """Сводка производительности всех ассистентов"""

        summary = {}

        for role in AssistantRole:
            summary[role.value] = {}

            for metric_type in MetricType:
                aggregated = self.db.get_aggregated_metrics(metric_type, hours_back)
                if aggregated:
                    summary[role.value][metric_type.value] = aggregated

        return summary
