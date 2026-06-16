
"""
Обучающие пайплайны для моделей машинного обучения.
Интеграция с Celery для background обучения и автоматического переобучения.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import optuna
import pandas as pd

# Celery для background задач (lazy — может быть не установлен)
try:
    from celery import Celery
    from celery import current_app as celery_app
    from celery.result import AsyncResult
    from celery.schedules import crontab
except ImportError:
    Celery = None  # type: ignore[assignment,misc]
    celery_app = None  # type: ignore[assignment]
    AsyncResult = None  # type: ignore[assignment,misc]
    crontab = None  # type: ignore[assignment]
from sklearn.feature_selection import SelectKBest, f_classif, f_regression

# ML библиотеки
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.ml.domain.predictor import ModelEnsemble, PredictionType, create_model
from src.modules.ml.infrastructure.metrics_collector import (
    AssistantRole,
    MetricsCollector,
)
from src.modules.ml.infrastructure.mlflow_manager import MLFlowManager

logger = StructuredLogger(__name__).logger


class TrainingStatus(Enum):
    """Статус обучения"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrainingType(Enum):
    """Типы обучения"""

    INITIAL = "initial"
    CONTINUOUS = "continuous"
    HYPERPARAMETER_TUNING = "hyperparameter_tuning"
    FEATURE_SELECTION = "feature_selection"
    ENSEMBLE_TRAINING = "ensemble_training"


@dataclass
class TrainingJob:
    """Job обучения модели"""

    job_id: str
    model_name: str
    model_type: str
    training_type: TrainingType
    status: TrainingStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    metrics: Optional[Dict[str, float]] = None
    model_path: Optional[str] = None
    error_message: Optional[str] = None


class DataPreprocessor:
    """Предобработка данных для обучения"""

    def __init__(self) -> None:
        self.scalers = {}
        self.encoders = {}
        self.feature_selectors = {}

    def prepare_features(
        self,
        df: pd.DataFrame,
        features: List[str],
        target: Optional[str] = None,
        preprocessing_config: Optional[Dict] = None,
    ) -> Tuple[pd.DataFrame, Optional[pd.Series]]:
        """Подготовка признаков"""

        preprocessing_config = preprocessing_config or {}

        # Выделение признаков и целевой переменной
        X = df[features].copy()
        y = df[target] if target else None

        # Заполнение пропущенных значений
        fill_method = preprocessing_config.get("fill_method", "median")
        for col in X.columns:
            if X[col].dtype in ["int64", "float64"]:
                if fill_method == "median":
                    X[col] = X[col].fillna(X[col].median())
                elif fill_method == "mean":
                    X[col] = X[col].fillna(X[col].mean())
                elif fill_method == "zero":
                    X[col] = X[col].fillna(0)
            else:
                X[col] = X[col].fillna("unknown")

        # Кодирование категориальных переменных
        categorical_encoding = preprocessing_config.get(
            "categorical_encoding", "label")
        if categorical_encoding == "label":
            for col in X.select_dtypes(include=["object"]).columns:
                if col not in self.encoders:
                    self.encoders[col] = LabelEncoder()
                    X[col] = self.encoders[col].fit_transform(X[col])
                else:
                    # Обработка новых категорий
                    X[col] = X[col].map(
                        lambda x: x if x in self.encoders[col].classes_ else "unknown")
                    # Добавляем новую категорию
                    unknown_class = len(self.encoders[col].classes_)
                    self.encoders[col].classes_ = np.append(
                        self.encoders[col].classes_, "unknown")
                    X[col] = X[col].map(
                        lambda x: (self.encoders[col].transform([x])[
                                   0] if x != "unknown" else unknown_class)
                    )

        # Нормализация числовых признаков
        normalize = preprocessing_config.get("normalize", True)
        if normalize:
            scaler = StandardScaler()
            numeric_cols = X.select_dtypes(include=[np.number]).columns
            X[numeric_cols] = scaler.fit_transform(X[numeric_cols])
            self.scalers["standard_scaler"] = scaler

        # Отбор признаков
        k_best = preprocessing_config.get("k_best_features")
        if k_best and y is not None:
            if self._get_prediction_type(y) == PredictionType.CLASSIFICATION:
                selector = SelectKBest(score_func=f_classif,
                                       k=min(k_best, len(features)))
            else:
                selector = SelectKBest(score_func=f_regression,
                                       k=min(k_best, len(features)))

            X_selected = selector.fit_transform(X, y)
            selected_features = [features[i]
                                 for i in selector.get_support(indices=True)]
            X = pd.DataFrame(
                X_selected, columns=selected_features, index=X.index)
            self.feature_selectors["k_best"] = selector

            logger.info(
                "Отобрано признаков",
                extra={
                    "selected_count": len(selected_features),
                    "total_count": len(features),
                },
            )

        return X, y

    def _get_prediction_type(self, y: pd.Series) -> str:
        """Определение типа задачи по целевой переменной"""

        if y.dtype == "object" or y.nunique() < 10:
            return PredictionType.CLASSIFICATION
        else:
            return PredictionType.REGRESSION


class ModelTrainer:
    """Основной класс для обучения моделей"""

    def __init__(
        self,
        mlflow_manager: Optional[MLFlowManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        celery_app: Optional[Celery] = None,
    ) -> None:
        self.mlflow_manager = mlflow_manager or MLFlowManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.celery_app = celery_app
        self.preprocessor = DataPreprocessor()
        self.active_jobs = {}
        self.logger = logging.getLogger(f"{__name__}.ModelTrainer")

    def create_training_job(
        self,
        model_name: str,
        model_type: str,
        features: List[str],
        target: str,
        training_data: pd.DataFrame,
        training_type: TrainingType = TrainingType.INITIAL,
        hyperparameters: Optional[Dict] = None,
        preprocessing_config: Optional[Dict] = None,
    ) -> str:
        """Создание job для обучения"""

        job_id = f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        job = TrainingJob(
            job_id=job_id,
            model_name=model_name,
            model_type=model_type,
            training_type=training_type,
            status=TrainingStatus.PENDING,
        )

        self.active_jobs[job_id] = job

        # Запуск Celery задачи
        if self.celery_app:
            task = self._train_model_task.delay(
                job_id=job_id,
                model_name=model_name,
                model_type=model_type,
                features=features,
                target=target,
                training_data=training_data.to_dict("records"),
                training_type=training_type.value,
                hyperparameters=hyperparameters,
                preprocessing_config=preprocessing_config,
            )
            job.celery_task_id = task.id

            logger.info("Создан Celery task для обучения",
                        extra={"task_id": task.id})

        return job_id

    def get_job_status(self, job_id: str) -> TrainingJob:
        """Получение статуса job"""

        if job_id not in self.active_jobs:
            raise ValueError(f"Job {job_id} не найден")

        job = self.active_jobs[job_id]

        # Обновляем статус из Celery если доступно
        if hasattr(job, "celery_task_id") and self.celery_app:
            task = AsyncResult(job.celery_task_id, app=self.celery_app)

            if task.ready():
                if task.successful():
                    job.status = TrainingStatus.COMPLETED
                    job.end_time = datetime.utcnow()
                    job.metrics = task.result
                else:
                    job.status = TrainingStatus.FAILED
                    job.error_message = str(task.info)
            elif task.state == "PROGRESS":
                job.status = TrainingStatus.RUNNING

        return job

    def train_model(
        self,
        model_name: str,
        model_type: str,
        features: List[str],
        target: str,
        training_data: pd.DataFrame,
        test_size: float = 0.2,
        validation_split: float = 0.2,
        hyperparameters: Optional[Dict] = None,
        preprocessing_config: Optional[Dict] = None,
        experiment_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Прямое обучение модели без Celery"""

        start_time = datetime.utcnow()

        try:
            # Предобработка данных
            X, y = self.preprocessor.prepare_features(
                training_data, features, target, preprocessing_config)

            # Определение типа задачи
            prediction_type = self.preprocessor._get_prediction_type(y)

            # Разделение данных
            if prediction_type == PredictionType.CLASSIFICATION:
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=test_size, stratify=y, random_state=42
                )
            else:
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=test_size, random_state=42)

            # Создание модели
            model = create_model(
                model_type=model_type,
                model_name=model_name,
                prediction_type=prediction_type,
                features=features,
                target=target,
                model_params=hyperparameters,
                mlflow_manager=self.mlflow_manager,
            )

            # Обучение
            model.fit(X_train, y_train)

            # Оценка модели
            train_metrics = model.evaluate(X_train, y_train)
            test_metrics = model.evaluate(X_test, y_test)

            # Логирование в MLflow
            if experiment_name:
                with self.mlflow_manager.start_experiment(experiment_name):
                    self.mlflow_manager.log_params(
                        {
                            "model_name": model_name,
                            "model_type": model_type,
                            "features_count": len(features),
                            "train_samples": len(X_train),
                            "test_samples": len(X_test),
                            "test_size": test_size,
                        }
                    )

                    all_metrics = {
                        **train_metrics,
                        **{f"test_{k}": v for k, v in test_metrics.items()},
                    }
                    self.mlflow_manager.log_metrics(all_metrics)

                    # Логирование модели
                    self.mlflow_manager.log_model(
                        model=model,
                        model_name=model_name,
                        model_type=model_type,
                        input_example=X_train.head(5).to_dict("records"),
                    )

            end_time = datetime.utcnow()
            training_duration = (end_time - start_time).total_seconds()

            result = {
                "model": model,
                "train_metrics": train_metrics,
                "test_metrics": test_metrics,
                "training_duration_seconds": training_duration,
                "features_used": features,
                "preprocessing_config": preprocessing_config,
            }

            # Сохранение метрик
            self.metrics_collector.record_user_satisfaction(
                assistant_role=AssistantRole.ARCHITECT,  # По умолчанию
                satisfaction_score=test_metrics.get(
                    "accuracy", test_metrics.get("r2_score", 0)),
                project_id="model_training",
                context={
                    "model_name": model_name,
                    "training_duration": training_duration,
                },
            )

            logger.info(
                "Модель обучена",
                extra={
                    "model_name": model_name,
                    "training_duration_seconds": round(training_duration, 2),
                },
            )

            return result

        except Exception as e:
            logger.error(
                "Ошибка обучения модели",
                extra={
                    "model_name": model_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    def hyperparameter_tuning(
        self,
        model_name: str,
        model_type: str,
        features: List[str],
        target: str,
        training_data: pd.DataFrame,
        param_space: Dict[str, Any],
        n_trials: int = 100,
        experiment_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Оптимизация гиперпараметров с Optuna"""

        start_time = datetime.utcnow()

        try:
            # Предобработка данных
            X, y = self.preprocessor.prepare_features(
                training_data, features, target)
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42)

            def objective(trial):
                """Целевая функция для оптимизации"""

                # Создание параметров для текущей попытки
                current_params = {}
                for param_name, param_config in param_space.items():
                    if param_config["type"] == "int":
                        current_params[param_name] = trial.suggest_int(
                            param_name, param_config["low"], param_config["high"]
                        )
                    elif param_config["type"] == "float":
                        current_params[param_name] = trial.suggest_float(
                            param_name, param_config["low"], param_config["high"]
                        )
                    elif param_config["type"] == "choice":
                        current_params[param_name] = trial.suggest_categorical(
                            param_name, param_config["choices"])

                # Создание и обучение модели
                model = create_model(
                    model_type=model_type,
                    model_name=f"{model_name}_trial_{trial.number}",
                    prediction_type=self.preprocessor._get_prediction_type(y),
                    features=features,
                    target=target,
                    model_params=current_params,
                )

                model.fit(X_train, y_train)

                # Оценка
                metrics = model.evaluate(X_test, y_test)

                # Возвращаем главную метрику для оптимизации
                if model.prediction_type == PredictionType.CLASSIFICATION:
                    return metrics.get("accuracy", 0)
                else:
                    return metrics.get("r2_score", 0)

            # Создание study и оптимизация
            study = optuna.create_study(direction="maximize")
            study.optimize(objective, n_trials=n_trials)

            # Обучение финальной модели с лучшими параметрами
            best_params = study.best_params
            final_model = create_model(
                model_type=model_type,
                model_name=model_name,
                prediction_type=self.preprocessor._get_prediction_type(y),
                features=features,
                target=target,
                model_params=best_params,
            )

            final_model.fit(X_train, y_train)
            final_metrics = final_model.evaluate(X_test, y_test)

            end_time = datetime.utcnow()
            tuning_duration = (end_time - start_time).total_seconds()

            result = {
                "best_params": best_params,
                "best_score": study.best_value,
                "model": final_model,
                "metrics": final_metrics,
                "tuning_duration_seconds": tuning_duration,
                "study_stats": {
                    "n_trials": n_trials,
                    "best_trial_number": study.best_trial.number,
                },
            }

            # Логирование результатов
            if experiment_name:
                with self.mlflow_manager.start_experiment(experiment_name):
                    self.mlflow_manager.log_params(best_params)
                    self.mlflow_manager.log_metrics(
                        {
                            "best_score": study.best_value,
                            "n_trials": n_trials,
                            "tuning_duration": tuning_duration,
                        }
                    )

                    self.mlflow_manager.log_model(
                        model=final_model, model_name=model_name, model_type=model_type)

            logger.info(
                "Гиперпараметры оптимизированы",
                extra={
                    "tuning_duration_seconds": round(tuning_duration, 2),
                    "best_score": round(study.best_value, 4),
                },
            )

            return result

        except Exception as e:
            logger.error(
                "Ошибка оптимизации гиперпараметров",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            raise

    def create_ensemble(
        self,
        model_configs: List[Dict[str, Any]],
        features: List[str],
        target: str,
        training_data: pd.DataFrame,
        ensemble_method: str = "average",
    ) -> ModelEnsemble:
        """Создание ансамбля моделей"""

        models = []

        for config in model_configs:
            model_result = self.train_model(
                model_name=config["name"],
                model_type=config["type"],
                features=features,
                target=target,
                training_data=training_data,
                hyperparameters=config.get("hyperparameters"),
                experiment_name=config.get("experiment_name"),
            )
            models.append(model_result["model"])

        ensemble = ModelEnsemble(
            models=models, ensemble_method=ensemble_method)

        logger.info(
            "Создан ансамбль моделей",
            extra={"models_count": len(
                models), "ensemble_method": ensemble_method},
        )

        return ensemble

    def schedule_continuous_training(self, cron_schedule: str = "0 2 * * *"):
        """Планирование непрерывного обучения через Celery"""

        if not self.celery_app:
            raise ValueError("Celery не инициализирован")

        @self.celery_app.on_after_configure.connect
        def setup_periodic_tasks(sender: Any, **kwargs: Any) -> None:
            """Настройка периодических задач"""

            sender.add_periodic_task(
                crontab(hour=2, minute=0),  # Ежедневно в 2:00
                self._retrain_all_models_task.s(),
                name="retrain_all_models",
            )

            sender.add_periodic_task(
                crontab(hour=6, minute=0),  # Каждые 6 часов
                self._update_feature_store_task.s(),
                name="update_feature_store",
            )

    def _train_model_task(self, job_id: str, **kwargs: Any) -> Dict[str, Any]:
        """Celery task для обучения модели"""

        training_data = pd.DataFrame(kwargs["training_data"])

        result = self.train_model(
            model_name=kwargs["model_name"],
            model_type=kwargs["model_type"],
            features=kwargs["features"],
            target=kwargs["target"],
            training_data=training_data,
            hyperparameters=kwargs.get("hyperparameters"),
            preprocessing_config=kwargs.get("preprocessing_config"),
            experiment_name=f"{kwargs['model_name']}_training",
        )

        return result

    def _retrain_all_models_task(self) -> Dict[str, Any]:
        """Переобучение всех моделей"""

        self.logger.info("Запуск переобучения всех моделей")

        # Здесь можно добавить логику переобучения всех моделей
        # на основе новых данных

        return {"status": "completed", "models_retrained": 0}

    def _update_feature_store_task(self) -> Dict[str, Any]:
        """Обновление Feature Store"""

        self.logger.info("Обновление Feature Store")

        # Обновление фичей для новых данных

        return {"status": "completed", "features_updated": 0}
