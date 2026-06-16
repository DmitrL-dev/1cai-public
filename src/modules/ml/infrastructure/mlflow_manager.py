
"""
MLflow менеджер для экспериментов и трекинга моделей.
Интеграция с MLflow для мониторинга экспериментов и управления моделями.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from src.config import settings
from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class MLFlowManager:
    """Менеджер MLflow экспериментов и моделей"""

    def __init__(self, tracking_uri: Optional[str] = None) -> None:
        """Инициализация MLflow клиента"""
        self.tracking_uri = tracking_uri or settings.MLFLOW_TRACKING_URI
        self.client = MlflowClient(tracking_uri=self.tracking_uri)

        # Установка tracking URI
        mlflow.set_tracking_uri(self.tracking_uri)

        # Настройка экспериментов
        self._setup_experiments()

        logger.info("MLflow инициализирован", extra={
                    "tracking_uri": self.tracking_uri})

    def _setup_experiments(self) -> None:
        """Создание и настройка экспериментов"""

        experiments = [
            {
                "name": "requirement_analysis",
                "description": "Модели предсказания сложности требований",
            },
            {
                "name": "risk_assessment",
                "description": "Модели оценки архитектурных рисков",
            },
            {
                "name": "architecture_patterns",
                "description": "Модели выбора архитектурных паттернов",
            },
            {
                "name": "recommendation_quality",
                "description": "Модели оценки качества рекомендаций",
            },
            {"name": "ab_testing", "description": "A/B тестирование моделей"},
        ]

        for exp_config in experiments:
            try:
                experiment_name = exp_config["name"]

                # Проверяем существование эксперимента
                try:
                    self.client.get_experiment_by_name(experiment_name)
                except MlflowException:
                    # Создаем новый эксперимент
                    experiment_id = self.client.create_experiment(
                        name=experiment_name,
                        tags={
                            "description": exp_config["description"],
                            "created_at": datetime.utcnow().isoformat(),
                        },
                    )
                    logger.info("Создан эксперимент", extra={
                                "experiment_name": experiment_name})

            except Exception as e:
                logger.error(
                    "Ошибка настройки эксперимента",
                    extra={
                        "experiment_name": exp_config["name"],
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )

    def start_experiment(self, experiment_name: str, run_name: Optional[str] = None) -> str:
        """Запуск нового эксперимента"""

        try:
            # Получаем или создаем эксперимент
            try:
                experiment = self.client.get_experiment_by_name(
                    experiment_name)
                experiment_id = experiment.experiment_id
            except MlflowException:
                experiment_id = self.client.create_experiment(experiment_name)

            # Запускаем новый run
            run = mlflow.start_run(
                experiment_id=experiment_id,
                run_name=run_name or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            )

            run_id = run.info.run_id
            logger.info(
                "Запущен эксперимент",
                extra={"experiment_name": experiment_name, "run_id": run_id},
            )

            return run_id

        except Exception as e:
            logger.error(
                "Ошибка запуска эксперимента",
                extra={
                    "experiment_name": experiment_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    def log_params(self, params: Dict[str, Any]) -> None:
        """Логирование параметров модели"""

        # Фильтруем параметры для MLflow
        filtered_params = {}
        for key, value in params.items():
            if isinstance(value, (int, float, str, bool)):
                filtered_params[key] = value
            elif isinstance(value, list) and len(value) <= 10:
                filtered_params[key] = json.dumps(value)
            elif isinstance(value, dict):
                filtered_params[key] = json.dumps(value)

        mlflow.log_params(filtered_params)
        logger.debug("Записаны параметры", extra={
                     "params_keys": list(filtered_params.keys())})

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None) -> None:
        """Логирование метрик"""

        # Фильтруем метрики
        filtered_metrics = {}
        for key, value in metrics.items():
            if isinstance(value, (int, float)) and not np.isnan(value):
                filtered_metrics[key] = float(value)

        if filtered_metrics:
            mlflow.log_metrics(filtered_metrics, step=step)
            logger.debug(
                "Записаны метрики",
                extra={"metrics_keys": list(filtered_metrics.keys())},
            )

    def log_artifacts(self, artifacts: Dict[str, Union[str, Path]], prefix: str = "") -> None:
        """Логирование артефактов"""

        for name, path in artifacts.items():
            try:
                artifact_name = f"{prefix}/{name}" if prefix else name
                mlflow.log_artifact(str(path), artifact_name)
                logger.debug("Записан артефакт", extra={
                             "artifact_name": artifact_name})
            except Exception as e:
                logger.error(
                    "Ошибка записи артефакта",
                    extra={
                        "artifact_name": name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )

    def log_model(
        self,
        model: Any,
        model_name: str,
        model_type: str,
        input_example: Optional[Any] = None,
        registered_model_name: Optional[str] = None,
    ) -> None:
        """Логирование модели"""

        try:
            # Определяем flavor модели
            model_flavor = self._detect_model_flavor(model_type)

            # Логируем модель с соответствующим flavor
            if model_flavor == "sklearn":
                mlflow.sklearn.log_model(
                    model,
                    model_name,
                    input_example=input_example,
                    registered_model_name=registered_model_name,
                )
            elif model_flavor == "tensorflow":
                import mlflow.tensorflow
                mlflow.tensorflow.log_model(
                    model,
                    model_name,
                    input_example=input_example,
                    registered_model_name=registered_model_name,
                )
            else:
                # Fallback для других типов моделей
                mlflow.sklearn.log_model(
                    model,
                    model_name,
                    input_example=input_example,
                    registered_model_name=registered_model_name,
                )

            logger.info("Модель записана в MLflow",
                        extra={"model_name": model_name})

        except Exception as e:
            logger.error(
                "Ошибка логирования модели",
                extra={
                    "model_name": model_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    def load_model(self, model_uri: str) -> Any:
        """Загрузка модели из MLflow"""

        try:
            model = mlflow.sklearn.load_model(model_uri)
            logger.info("Модель загружена", extra={"model_uri": model_uri})
            return model
        except Exception as e:
            logger.error(
                "Ошибка загрузки модели",
                extra={
                    "model_uri": model_uri,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    def register_model(self, run_id: str, model_name: str) -> Any:
        """Регистрация модели в MLflow Model Registry"""

        try:
            model_uri = f"runs:/{run_id}/model"

            # Создаем или обновляем модель в registry
            model_version = mlflow.register_model(
                model_uri=model_uri, name=model_name)

            logger.info(
                "Модель зарегистрирована",
                extra={"model_name": model_name,
                       "version": model_version.version},
            )

            return model_version

        except Exception as e:
            logger.error(
                "Ошибка регистрации модели",
                extra={
                    "model_name": model_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    def get_experiment_metrics(self, experiment_name: str, limit: int = 10) -> pd.DataFrame:
        """Получение метрик экспериментов"""

        try:
            # Получаем эксперимент
            experiment = self.client.get_experiment_by_name(experiment_name)

            # Получаем последние runs
            runs = self.client.search_runs(
                experiment_ids=[experiment.experiment_id],
                order_by=["start_time DESC"],
                max_results=limit,
            )

            # Подготавливаем данные
            data = []
            for run in runs:
                run_data = {
                    "run_id": run.info.run_id,
                    "start_time": run.info.start_time,
                    "status": run.info.status,
                    "artifact_uri": run.info.artifact_uri,
                }

                # Добавляем метрики
                for key, value in run.data.metrics.items():
                    run_data[f"metric_{key}"] = value

                # Добавляем параметры
                for key, value in run.data.params.items():
                    run_data[f"param_{key}"] = value

                data.append(run_data)

            df = pd.DataFrame(data)
            logger.debug(
                "Получено runs из эксперимента",
                extra={"runs_count": len(
                    df), "experiment_name": experiment_name},
            )

            return df

        except Exception as e:
            logger.error(
                "Ошибка получения метрик эксперимента",
                extra={
                    "experiment_name": experiment_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    def compare_models(self, model_names: List[str]) -> Dict[str, Any]:
        """Сравнение моделей"""

        comparison_results = {}

        for model_name in model_names:
            try:
                # Получаем последние версии моделей
                model_versions = self.client.search_model_versions(
                    f"name='{model_name}'")

                if model_versions:
                    latest_version = model_versions[0]
                    model_uri = f"models:/{model_name}/{latest_version.version}"

                    # Загружаем метаданные модели
                    self.client.get_model_version(
                        model_name, latest_version.version)

                    comparison_results[model_name] = {
                        "version": latest_version.version,
                        "creation_timestamp": latest_version.creation_timestamp,
                        "last_updated_timestamp": latest_version.last_updated_timestamp,
                        "current_stage": latest_version.current_stage,
                        "description": latest_version.description,
                    }

            except Exception as e:
                logger.error(
                    "Ошибка сравнения модели",
                    extra={
                        "model_name": model_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
                comparison_results[model_name] = {"error": str(e)}

        return comparison_results

    def promote_model(self, model_name: str, version: str, stage: str) -> None:
        """Перевод модели в продакшен"""

        try:
            self.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage=stage,
                archive_existing_versions=True,
            )

            logger.info(
                "Модель переведена в стадию",
                extra={"model_name": model_name,
                       "version": version, "stage": stage},
            )

        except Exception as e:
            logger.error(
                "Ошибка перевода модели в продакшен",
                extra={
                    "model_name": model_name,
                    "version": version,
                    "stage": stage,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    def log_dataframe(self, df: pd.DataFrame, name: str) -> None:
        """Логирование DataFrame как артефакт"""

        try:
            # Создаем временный файл
            with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
                df.to_csv(f.name, index=False)
                mlflow.log_artifact(f.name, f"data/{name}.csv")

            logger.debug("DataFrame записан в MLflow",
                         extra={"dataframe_name": name})

        except Exception as e:
            logger.error(
                "Ошибка логирования DataFrame",
                extra={
                    "dataframe_name": name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    def _detect_model_flavor(self, model_type: str) -> str:
        """Определение MLflow flavor для модели"""

        model_type_lower = model_type.lower()

        if model_type_lower in ["sklearn", "scikit-learn", "xgboost", "lightgbm"]:
            return "sklearn"
        elif model_type_lower in ["tensorflow", "keras", "tf"]:
            return "tensorflow"
        elif model_type_lower in ["pytorch", "torch"]:
            return "pytorch"
        else:
            return "sklearn"  # Default fallback

    def create_feature_store_experiment(self, features: pd.DataFrame, name: str) -> None:
        """Создание эксперимента для Feature Store"""

        try:
            experiment_name = f"feature_store_{name}"

            # Запускаем эксперимент
            self.start_experiment(
                experiment_name, f"features_{datetime.now().strftime('%Y%m%d')}")

            # Логируем статистики фич
            feature_stats = {}
            for col in features.columns:
                if features[col].dtype in ["int64", "float64"]:
                    feature_stats[f"{col}_mean"] = float(features[col].mean())
                    feature_stats[f"{col}_std"] = float(features[col].std())
                    feature_stats[f"{col}_min"] = float(features[col].min())
                    feature_stats[f"{col}_max"] = float(features[col].max())

            self.log_metrics(feature_stats)

            # Логируем фичи как артефакт
            self.log_dataframe(features, f"{name}_features")

            # Завершаем run
            mlflow.end_run()

            logger.info(
                "Feature Store эксперимент создан",
                extra={"experiment_name": experiment_name},
            )

        except Exception as e:
            logger.error(
                "Ошибка создания Feature Store эксперимента",
                extra={
                    "experiment_name": experiment_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    def close_experiment(self, run_id: Optional[str] = None) -> None:
        """Завершение эксперимента"""

        try:
            mlflow.end_run(run_id)
            logger.debug("Эксперимент завершен", extra={
                         "run_id": run_id or "текущий"})
        except Exception as e:
            logger.error(
                "Ошибка завершения эксперимента",
                extra={
                    "run_id": run_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
