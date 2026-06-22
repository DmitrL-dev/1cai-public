"""
A/B тестирование для ML моделей.
Позволяет тестировать новые модели в продакшене с минимальными рисками.
"""

import hashlib
import json
import logging
import math
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Статистика
from scipy import stats

# База данных для результатов A/B тестов
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.ml.domain.predictor import MLPredictor
from src.modules.ml.infrastructure.metrics_collector import MetricsCollector
from src.modules.ml.infrastructure.mlflow_manager import MLFlowManager

logger = StructuredLogger(__name__).logger
Base = declarative_base()


class ABTestStatus(Enum):
    """Статус A/B теста"""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TestType(Enum):
    """Типы A/B тестов"""

    MODEL_COMPARISON = "model_comparison"
    FEATURE_TEST = "feature_test"
    HYPERPARAMETER_TEST = "hyperparameter_test"
    THRESHOLD_TEST = "threshold_test"


@dataclass
class ABTestConfig:
    """Конфигурация A/B теста"""

    test_name: str
    description: str
    test_type: TestType
    control_model: MLPredictor
    treatment_model: MLPredictor
    traffic_split: float  # 0.0 - 1.0, доля трафика для treatment
    primary_metric: str
    success_criteria: Dict[str, float]
    duration_days: int
    min_sample_size: int
    significance_level: float = 0.05


@dataclass
class ABTestResult:
    """Результат A/B теста"""

    test_id: str
    control_metric: float
    treatment_metric: float
    improvement: float
    p_value: float
    confidence_interval: Tuple[float, float]
    is_significant: bool
    power: float
    sample_size_control: int
    sample_size_treatment: int


class ABTestRecord(Base):
    """Модель записи A/B теста в БД"""

    __tablename__ = "ab_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_name = Column(String, nullable=False)
    test_type = Column(String, nullable=False)
    status = Column(String, nullable=False)

    # Конфигурация
    traffic_split = Column(Float, nullable=False)
    primary_metric = Column(String, nullable=False)
    success_criteria = Column(JSON, nullable=False)
    duration_days = Column(Integer, nullable=False)
    min_sample_size = Column(Integer, nullable=False)
    significance_level = Column(Float, nullable=False)

    # Модели
    control_model_id = Column(String, nullable=False)
    treatment_model_id = Column(String, nullable=False)

    # Статистика
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    sample_size_control = Column(Integer, default=0)
    sample_size_treatment = Column(Integer, default=0)

    # Результаты
    control_metric_mean = Column(Float)
    treatment_metric_mean = Column(Float)
    improvement = Column(Float)
    p_value = Column(Float)
    confidence_interval_low = Column(Float)
    confidence_interval_high = Column(Float)
    is_significant = Column(Boolean)
    power = Column(Float)

    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ABTestSession(Base):
    """Запись сессии A/B теста"""

    __tablename__ = "ab_test_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = Column(UUID(as_uuid=True), nullable=False)
    session_id = Column(String, nullable=False)
    user_id = Column(String)
    group = Column(String, nullable=False)  # 'control' или 'treatment'
    assigned_model = Column(String, nullable=False)

    # Результаты
    predicted_value = Column(Float)
    actual_value = Column(Float)
    prediction_error = Column(Float)
    user_feedback = Column(Float)
    response_time = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)


class ABTestingDatabase:
    """БД для A/B тестов"""

    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        Base.metadata.create_all(bind=self.engine)

    def create_ab_test(self, config: ABTestConfig) -> str:
        """Создание нового A/B теста"""
        session = self.SessionLocal()
        try:
            test_record = ABTestRecord(
                test_name=config.test_name,
                test_type=config.test_type.value,
                status=ABTestStatus.DRAFT.value,
                traffic_split=config.traffic_split,
                primary_metric=config.primary_metric,
                success_criteria=json.dumps(config.success_criteria),
                duration_days=config.duration_days,
                min_sample_size=config.min_sample_size,
                significance_level=config.significance_level,
                control_model_id=config.control_model.model_name,
                treatment_model_id=config.treatment_model.model_name,
            )

            session.add(test_record)
            session.commit()

            logger.info("Создан A/B тест", extra={"test_name": config.test_name})
            return str(test_record.id)
        finally:
            session.close()

    def get_test_status(self, test_id: str) -> Optional[Dict]:
        """Получение статуса теста"""
        session = self.SessionLocal()
        try:
            test = (
                session.query(ABTestRecord).filter(ABTestRecord.id == test_id).first()
            )

            if test:
                return asdict(test)
            return None
        finally:
            session.close()

    def update_test_metrics(self, test_id: str, result: ABTestResult) -> None:
        """Обновление метрик теста"""
        session = self.SessionLocal()
        try:
            test = (
                session.query(ABTestRecord).filter(ABTestRecord.id == test_id).first()
            )

            if test:
                test.sample_size_control = result.sample_size_control
                test.sample_size_treatment = result.sample_size_treatment
                test.control_metric_mean = result.control_metric
                test.treatment_metric_mean = result.treatment_metric
                test.improvement = result.improvement
                test.p_value = result.p_value
                test.confidence_interval_low = result.confidence_interval[0]
                test.confidence_interval_high = result.confidence_interval[1]
                test.is_significant = result.is_significant
                test.power = result.power
                test.updated_at = datetime.utcnow()

                session.commit()
        finally:
            session.close()

    def log_test_session(self, test_id: str, session_data: Dict[str, Any]) -> None:
        """Логирование сессии теста"""
        session = self.SessionLocal()
        try:
            test_session = ABTestSession(
                test_id=test_id,
                session_id=session_data["session_id"],
                user_id=session_data.get("user_id"),
                group=session_data["group"],
                assigned_model=session_data["assigned_model"],
                predicted_value=session_data.get("predicted_value"),
                actual_value=session_data.get("actual_value"),
                prediction_error=session_data.get("prediction_error"),
                user_feedback=session_data.get("user_feedback"),
                response_time=session_data.get("response_time"),
            )

            session.add(test_session)
            session.commit()
        finally:
            session.close()

    def get_test_data(self, test_id: str) -> Tuple[List[float], List[float]]:
        """Получение данных для анализа теста"""
        session = self.SessionLocal()
        try:
            # Получаем данные контрольной группы
            control_data = (
                session.query(ABTestSession.actual_value)
                .filter(
                    ABTestSession.test_id == test_id, ABTestSession.group == "control"
                )
                .all()
            )

            # Получаем данные treatment группы
            treatment_data = (
                session.query(ABTestSession.actual_value)
                .filter(
                    ABTestSession.test_id == test_id, ABTestSession.group == "treatment"
                )
                .all()
            )

            return [row[0] for row in control_data], [row[0] for row in treatment_data]
        finally:
            session.close()


class ABTestManager:
    """Менеджер A/B тестирования"""

    def __init__(
        self,
        database_url: str,
        mlflow_manager: Optional[MLFlowManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ) -> None:
        self.db = ABTestingDatabase(database_url)
        self.mlflow_manager = mlflow_manager or MLFlowManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.active_tests = {}
        self.logger = logging.getLogger(f"{__name__}.ABTestManager")

    def create_ab_test(self, config: ABTestConfig) -> str:
        """Создание A/B теста"""

        # Проверка валидности конфигурации
        if not 0 <= config.traffic_split <= 1:
            raise ValueError("traffic_split должен быть в диапазоне [0, 1]")

        if not 0 < config.significance_level < 1:
            raise ValueError("significance_level должен быть в диапазоне (0, 1)")

        # Создание теста в БД
        test_id = self.db.create_ab_test(config)

        # Сохранение в активных тестах
        self.active_tests[test_id] = config

        logger.info(
            "Создан A/B тест", extra={"test_name": config.test_name, "test_id": test_id}
        )

        return test_id

    def assign_model_to_user(
        self, test_id: str, user_id: str, session_id: str
    ) -> Dict[str, Any]:
        """Назначение модели пользователю"""

        if test_id not in self.active_tests:
            raise ValueError(f"A/B тест {test_id} не найден или не активен")

        config = self.active_tests[test_id]

        # Определение группы на основе пользователя (консистентное назначение)
        user_hash = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        treatment_threshold = config.traffic_split * 1000000

        if user_hash % 1000000 < treatment_threshold:
            group = "treatment"
            model = config.treatment_model
        else:
            group = "control"
            model = config.control_model

        # Логирование назначения
        self.db.log_test_session(
            test_id,
            {
                "session_id": session_id,
                "user_id": user_id,
                "group": group,
                "assigned_model": model.model_name,
            },
        )

        return {"group": group, "model": model, "model_name": model.model_name}

    def log_prediction_result(
        self,
        test_id: str,
        session_id: str,
        predicted_value: Optional[float] = None,
        actual_value: Optional[float] = None,
        user_feedback: Optional[float] = None,
        response_time: Optional[float] = None,
    ) -> None:
        """Логирование результата предсказания"""

        session = self.db.SessionLocal()
        try:
            # Находим сессию
            test_session = (
                session.query(ABTestSession)
                .filter(
                    ABTestSession.test_id == test_id,
                    ABTestSession.session_id == session_id,
                )
                .first()
            )

            if test_session:
                test_session.predicted_value = predicted_value
                test_session.actual_value = actual_value
                test_session.user_feedback = user_feedback
                test_session.response_time = response_time

                # Вычисляем ошибку предсказания
                if predicted_value is not None and actual_value is not None:
                    test_session.prediction_error = abs(predicted_value - actual_value)

                session.commit()
        finally:
            session.close()

    def analyze_test_results(self, test_id: str) -> ABTestResult:
        """Анализ результатов A/B теста"""

        # Получение данных
        control_data, treatment_data = self.db.get_test_data(test_id)

        if len(control_data) < 10 or len(treatment_data) < 10:
            raise ValueError("Недостаточно данных для анализа")

        # Вычисление метрик
        control_metric = np.mean(control_data)
        treatment_metric = np.mean(treatment_data)

        # Статистический тест (t-тест)
        if len(control_data) >= 2 and len(treatment_data) >= 2:
            t_stat, p_value = stats.ttest_ind(control_data, treatment_data)
        else:
            p_value = 1.0

        # Доверительный интервал
        diff_mean = treatment_metric - control_metric
        pooled_std = math.sqrt(
            (np.var(control_data) / len(control_data))
            + (np.var(treatment_data) / len(treatment_data))
        )

        # 95% доверительный интервал
        confidence_level = 0.95
        t_critical = stats.t.ppf(
            (1 + confidence_level) / 2, df=len(control_data) + len(treatment_data) - 2
        )

        margin_error = t_critical * pooled_std
        confidence_interval = (diff_mean - margin_error, diff_mean + margin_error)

        # Мощность теста
        power = self._calculate_power(
            len(control_data), len(treatment_data), diff_mean, pooled_std
        )

        # Статистическая значимость
        is_significant = p_value < 0.05

        # Создание результата
        result = ABTestResult(
            test_id=test_id,
            control_metric=control_metric,
            treatment_metric=treatment_metric,
            improvement=(treatment_metric - control_metric) / control_metric * 100,
            p_value=p_value,
            confidence_interval=confidence_interval,
            is_significant=is_significant,
            power=power,
            sample_size_control=len(control_data),
            sample_size_treatment=len(treatment_data),
        )

        # Обновление в БД
        self.db.update_test_metrics(test_id, result)

        # Логирование в MLflow
        self._log_test_results_to_mlflow(test_id, result)

        self.logger.info(
            f"Анализ A/B теста {test_id}: "
            f"improvement={result.improvement:.2f}%, "
            f"p_value={result.p_value:.4f}, "
            f"significant={result.is_significant}"
        )

        return result

    def _calculate_power(
        self, n_control: int, n_treatment: int, effect_size: float, pooled_std: float
    ) -> float:
        """Расчет мощности статистического теста"""

        # Стандартизированный размер эффекта
        cohen_d = effect_size / pooled_std if pooled_std > 0 else 0

        if cohen_d == 0:
            return 0.0

        # Приближенный расчет мощности для t-теста
        n_pooled = (n_control * n_treatment) / (n_control + n_treatment)
        z_effect = cohen_d * math.sqrt(n_pooled / 2)

        # Мощность (приближенно)
        power = 1 - stats.norm.cdf(1.96 - z_effect) + stats.norm.cdf(-1.96 - z_effect)

        return min(max(power, 0.0), 1.0)

    def _log_test_results_to_mlflow(self, test_id: str, result: ABTestResult) -> None:
        """Логирование результатов в MLflow"""

        try:
            with self.mlflow_manager.start_experiment("ab_testing"):
                metrics = {
                    "control_metric": result.control_metric,
                    "treatment_metric": result.treatment_metric,
                    "improvement_percent": result.improvement,
                    "p_value": result.p_value,
                    "confidence_interval_low": result.confidence_interval[0],
                    "confidence_interval_high": result.confidence_interval[1],
                    "is_significant": result.is_significant,
                    "power": result.power,
                    "sample_size_control": result.sample_size_control,
                    "sample_size_treatment": result.sample_size_treatment,
                }

                self.mlflow_manager.log_metrics(metrics)
        except Exception as e:
            logger.error(
                "Ошибка логирования в MLflow",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )

    def should_continue_test(self, test_id: str) -> Tuple[bool, str]:
        """Определение необходимости продолжения теста"""

        config = self.active_tests.get(test_id)
        if not config:
            return False, "Тест не найден"

        status = self.db.get_test_status(test_id)
        if not status:
            return False, "Статус теста не найден"

        # Проверка завершения по времени
        if status["start_time"]:
            elapsed_days = (datetime.utcnow() - status["start_time"]).days
            if elapsed_days >= config.duration_days:
                return False, "Тест завершен по времени"

        # Проверка минимального размера выборки
        total_samples = status["sample_size_control"] + status["sample_size_treatment"]
        if total_samples >= config.min_sample_size:
            return False, "Достигнут минимальный размер выборки"

        # Проверка статистической мощности
        if status["power"] and status["power"] >= 0.8:
            return False, "Достаточная мощность теста"

        return True, "Тест продолжается"

    def promote_winning_model(self, test_id: str) -> MLPredictor:
        """Продвижение выигрышной модели в продакшен"""

        result = self.analyze_test_results(test_id)
        config = self.active_tests[test_id]

        if result.is_significant and result.improvement > 0:
            winning_model = config.treatment_model
            message = f"Treatment модель выиграла: улучшение {result.improvement:.2f}%"
        else:
            winning_model = config.control_model
            message = f"Control модель остается: улучшение {result.improvement:.2f}%"

        # Здесь можно добавить логику продвижения модели в продакшен
        # Например, обновление конфигурации сервиса

        logger.info("Продвижение модели", extra={"message": message})

        # Обновление статуса теста
        session = self.db.SessionLocal()
        try:
            test = (
                session.query(ABTestRecord).filter(ABTestRecord.id == test_id).first()
            )

            if test:
                test.status = ABTestStatus.COMPLETED.value
                test.end_time = datetime.utcnow()
                session.commit()
        finally:
            session.close()

        return winning_model

    def get_test_summary(self, test_id: str) -> Dict[str, Any]:
        """Получение сводки по тесту"""

        status = self.db.get_test_status(test_id)
        if not status:
            raise ValueError(f"Тест {test_id} не найден")

        result = None
        try:
            result = self.analyze_test_results(test_id)
        except (ValueError, KeyError, AttributeError):
            pass  # Тест может еще не иметь достаточно данных

        summary = {
            "test_id": test_id,
            "test_name": status["test_name"],
            "status": status["status"],
            "start_time": status["start_time"],
            "duration_days": status["duration_days"],
            "sample_size_control": status["sample_size_control"],
            "sample_size_treatment": status["sample_size_treatment"],
            "primary_metric": status["primary_metric"],
        }

        if result:
            summary.update(
                {
                    "control_metric": result.control_metric,
                    "treatment_metric": result.treatment_metric,
                    "improvement_percent": result.improvement,
                    "p_value": result.p_value,
                    "is_significant": result.is_significant,
                    "confidence_interval": result.confidence_interval,
                }
            )

        return summary
