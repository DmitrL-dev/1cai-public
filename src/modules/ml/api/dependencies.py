from typing import Any, Dict, Optional

from src.config import settings
from src.modules.ml.services.ab_test_service import ABTestService
from src.modules.ml.services.metrics_service import MetricsService
from src.modules.ml.services.mlflow_service import MLFlowService
from src.modules.ml.services.training_service import TrainingService

# Global state (in-memory storage for MVP)
trained_models: Dict[str, Any] = {}
active_ab_tests: Dict[str, str] = {}

# Service singletons
_metrics_service: Optional[MetricsService] = None
_training_service: Optional[TrainingService] = None
_mlflow_service: Optional[MLFlowService] = None
_ab_test_service: Optional[ABTestService] = None


def get_ml_services():
    """Dependency for getting ML services."""
    global _metrics_service, _training_service, _mlflow_service, _ab_test_service

    if _metrics_service is None:
        _metrics_service = MetricsService()

    if _mlflow_service is None:
        _mlflow_service = MLFlowService()

    if _training_service is None:
        _training_service = TrainingService()

    if _ab_test_service is None:
        _ab_test_service = ABTestService(
            database_url=settings.DATABASE_URL,
            mlflow_manager=_mlflow_service,
            metrics_collector=_metrics_service,
        )

    return {
        "metrics_collector": _metrics_service,
        "model_trainer": _training_service,
        "mlflow_manager": _mlflow_service,
        "ab_test_manager": _ab_test_service,
    }
