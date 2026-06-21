# [NEXUS IDENTITY] ID: 3135880199165626437 | DATE: 2025-11-19

"""
Base classes for ML prediction models.
Integration layer for scikit-learn prediction types.
"""

import pickle
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

# ML models
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)

# TensorFlow removed — was never in requirements.txt (dead code)
# PyTorch removed — not needed for sklearn-based ML pipeline

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.ml.infrastructure.mlflow_manager import MLFlowManager

logger = StructuredLogger(__name__).logger


class PredictionType:
    """Prediction type constants."""

    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    RECOMMENDATION = "recommendation"


class MLPredictor(ABC):
    """Abstract base class for ML predictors."""

    def __init__(
        self,
        model_name: str,
        prediction_type: str,
        features: List[str],
        target: Optional[str] = None,
        mlflow_manager: Optional[MLFlowManager] = None,
    ):
        self.model_name = model_name
        self.prediction_type = prediction_type
        self.features = features
        self.target = target
        self.mlflow_manager = mlflow_manager
        self.model = None
        self.is_trained = False

        # Model configuration
        self.config = {
            "model_name": model_name,
            "prediction_type": prediction_type,
            "features": features,
            "target": target,
            "created_at": datetime.utcnow().isoformat(),
        }

        logger.info("Initialized MLPredictor", extra={"model_name": model_name})

    @abstractmethod
    def fit(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Optional[Union[pd.Series, np.ndarray]] = None,
    ) -> "MLPredictor":
        """Train the model."""

    @abstractmethod
    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[np.ndarray, pd.DataFrame]:
        """Run prediction."""

    @abstractmethod
    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> Optional[np.ndarray]:
        """Run probability prediction for classifiers."""

    def save_model(self, filepath: str):
        """Save model to disk."""
        try:
            model_data = {
                "config": self.config,
                "is_trained": self.is_trained,
                "model": self.model,
                "features": self.features,
                "target": self.target,
            }

            with open(filepath, "wb") as f:
                pickle.dump(model_data, f)

            logger.info(
                "Model saved",
                extra={"model_name": self.model_name, "filepath": filepath},
            )

        except Exception as e:
            logger.error(
                "Model save failed",
                extra={
                    "model_name": self.model_name,
                    "filepath": filepath,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    def load_model(self, filepath: str):
        """Load model from disk."""
        try:
            with open(filepath, "rb") as f:
                model_data = pickle.load(f)

            self.config = model_data["config"]
            self.model = model_data["model"]
            self.is_trained = model_data["is_trained"]
            self.features = model_data["features"]
            self.target = model_data["target"]

            logger.info(
                "Model loaded",
                extra={"model_name": self.model_name, "filepath": filepath},
            )

        except Exception as e:
            logger.error(
                "Model load failed",
                extra={
                    "model_name": self.model_name,
                    "filepath": filepath,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    def evaluate(self, X: Union[pd.DataFrame, np.ndarray], y: Union[pd.Series, np.ndarray]) -> Dict[str, float]:
        """Evaluate model quality."""

        if not self.is_trained:
            raise ValueError("Model is not trained")

        predictions = self.predict(X)

        metrics = {}

        if self.prediction_type == PredictionType.CLASSIFICATION:
            metrics.update(
                {
                    "accuracy": accuracy_score(y, predictions),
                    "precision": precision_score(y, predictions, average="weighted"),
                    "recall": recall_score(y, predictions, average="weighted"),
                    "f1_score": f1_score(y, predictions, average="weighted"),
                }
            )

        elif self.prediction_type == PredictionType.REGRESSION:
            metrics.update(
                {
                    "mse": mean_squared_error(y, predictions),
                    "rmse": np.sqrt(mean_squared_error(y, predictions)),
                    "r2_score": r2_score(y, predictions),
                }
            )

        logger.info("Model evaluated", extra={"model_name": self.model_name, "metrics": metrics})

        return metrics

    def log_model_metrics_to_mlflow(self, metrics: Dict[str, float], run_id: Optional[str] = None):
        """Log metrics to MLflow when a manager is configured."""

        if self.mlflow_manager:
            self.mlflow_manager.log_metrics(metrics)

    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """Return feature importance when the underlying model exposes it."""

        if hasattr(self.model, "feature_importances_"):
            return dict(zip(self.features, self.model.feature_importances_))
        elif hasattr(self.model, "coef_"):
            importance = (
                np.abs(self.model.coef_[0]) if len(
                    self.model.coef_.shape) == 1 else np.abs(self.model.coef_[0])
            )
            return dict(zip(self.features, importance))

        return None

    def explain_prediction(self, X: Union[pd.DataFrame, np.ndarray], index: int = 0) -> Dict[str, Any]:
        """Explain one prediction using available feature importance."""

        if not self.is_trained:
            raise ValueError("Model is not trained")

        if isinstance(X, pd.DataFrame):
            sample = X.iloc[index].to_dict()
        else:
            sample = dict(zip(self.features, X[index]))

        # Basic interpretation based on feature importance.
        importance = self.get_feature_importance()

        explanation = {
            "sample": sample,
            "prediction": None,
            "feature_importance": importance,
            "contributing_features": [],
        }

        if importance:
            sorted_features = sorted(
                importance.items(), key=lambda x: x[1], reverse=True)
            # Top 5 features
            explanation["contributing_features"] = sorted_features[:5]

        return explanation


class SklearnPredictor(MLPredictor):
    """scikit-learn predictor implementation."""

    def __init__(
        self,
        model_name: str,
        prediction_type: str,
        features: List[str],
        target: Optional[str] = None,
        model_class: Optional[type] = None,
        model_params: Optional[Dict] = None,
        mlflow_manager: Optional[MLFlowManager] = None,
    ):
        super().__init__(model_name, prediction_type, features, target, mlflow_manager)

        self.model_class = model_class or self._get_default_model_class(
            prediction_type)
        self.model_params = model_params or {}

        logger.info(
            "Initialized SklearnPredictor",
            extra={"model_name": model_name,
                   "model_class": self.model_class.__name__},
        )

    def _get_default_model_class(self, prediction_type: str) -> type:
        """Return default model class for a prediction type."""

        if prediction_type == PredictionType.CLASSIFICATION:
            return RandomForestClassifier
        elif prediction_type == PredictionType.REGRESSION:
            return RandomForestRegressor
        else:
            return RandomForestClassifier

    def fit(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Optional[Union[pd.Series, np.ndarray]] = None,
    ) -> "SklearnPredictor":
        """Train the model."""

        try:
            # Prepare input data.
            if isinstance(X, pd.DataFrame):
                X_processed = X[self.features].fillna(0)
            else:
                X_processed = pd.DataFrame(X, columns=self.features).fillna(0)

            # Create and train the model.
            self.model = self.model_class(**self.model_params)
            self.model.fit(X_processed, y)

            self.is_trained = True

            logger.info(
                "Model trained",
                extra={
                    "model_name": self.model_name,
                    "samples_count": len(X_processed),
                },
            )

            return self

        except Exception as e:
            logger.error(
                "Model training failed",
                extra={
                    "model_name": self.model_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[np.ndarray, pd.DataFrame]:
        """Run prediction."""

        if not self.is_trained:
            raise ValueError("Model is not trained")

        try:
            # Prepare input data.
            if isinstance(X, pd.DataFrame):
                X_processed = X[self.features].fillna(0)
            else:
                X_processed = pd.DataFrame(X, columns=self.features).fillna(0)

            predictions = self.model.predict(X_processed)

            logger.debug("Prediction completed", extra={"samples_count": len(X_processed)})

            return predictions

        except Exception as e:
            logger.error(
                "Prediction failed",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            raise

    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> Optional[np.ndarray]:
        """Run probability prediction."""

        if not self.is_trained or not hasattr(self.model, "predict_proba"):
            return None

        try:
            # Prepare input data.
            if isinstance(X, pd.DataFrame):
                X_processed = X[self.features].fillna(0)
            else:
                X_processed = pd.DataFrame(X, columns=self.features).fillna(0)

            probabilities = self.model.predict_proba(X_processed)

            logger.debug("Probabilities computed", extra={"samples_count": len(X_processed)})

            return probabilities

        except Exception as e:
            logger.error(
                "Probability computation failed",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return None


# TensorFlowPredictor removed - tensorflow was never in requirements.txt
# 230 lines of dead code deleted. Use SklearnPredictor instead.
#
# To restore: git checkout v4.0-pre-cleanup -- src/modules/ml/domain/predictor.py

class ModelEnsemble:
    """Ensemble of ML models for stronger predictions."""

    def __init__(self, models: List[MLPredictor], ensemble_method: str = "average"):
        self.models = models
        self.ensemble_method = ensemble_method

        logger.info(
            "Model ensemble created",
            extra={"models_count": len(
                models), "ensemble_method": ensemble_method},
        )

    def fit(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Optional[Union[pd.Series, np.ndarray]] = None,
    ) -> "ModelEnsemble":
        """Train all models in the ensemble."""

        for model in self.models:
            model.fit(X, y)

        logger.info("All ensemble models trained")
        return self

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[np.ndarray, pd.DataFrame]:
        """Run ensemble prediction."""

        predictions = []

        for model in self.models:
            pred = model.predict(X)
            predictions.append(pred)

        # Combine predictions.
        if self.ensemble_method == "average":
            ensemble_pred = np.mean(predictions, axis=0)
        elif self.ensemble_method == "majority_vote":
            # Classification uses a majority-vote approximation.
            if self.models[0].prediction_type == PredictionType.CLASSIFICATION:
                ensemble_pred = np.round(np.mean(predictions, axis=0))
            else:
                ensemble_pred = np.mean(predictions, axis=0)
        else:
            ensemble_pred = predictions[0]  # Fallback

        return ensemble_pred

    def predict_with_uncertainty(self, X: Union[pd.DataFrame, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        """Return ensemble prediction with uncertainty estimate."""

        predictions = []

        for model in self.models:
            pred = model.predict(X)
            predictions.append(pred)

        predictions = np.array(predictions)

        # Mean prediction.
        mean_pred = np.mean(predictions, axis=0)

        # Standard deviation as uncertainty measure.
        uncertainty = np.std(predictions, axis=0)

        return mean_pred, uncertainty

    def evaluate_ensemble(
        self, X: Union[pd.DataFrame, np.ndarray], y: Union[pd.Series, np.ndarray]
    ) -> Dict[str, float]:
        """Evaluate ensemble quality."""

        ensemble_metrics = {}
        individual_metrics = {}

        # Evaluate individual models.
        for i, model in enumerate(self.models):
            try:
                metrics = model.evaluate(X, y)
                individual_metrics[f"model_{i}"] = metrics
            except Exception as e:
                logger.warning(
                    "Model evaluation failed",
                    extra={
                        "model_index": i,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )

        # Evaluate ensemble.
        try:
            ensemble_pred = self.predict(X)

            if self.models[0].prediction_type == PredictionType.CLASSIFICATION:
                ensemble_metrics["ensemble_accuracy"] = accuracy_score(
                    y, ensemble_pred)
            else:
                ensemble_metrics["ensemble_r2"] = r2_score(y, ensemble_pred)
                ensemble_metrics["ensemble_rmse"] = np.sqrt(
                    mean_squared_error(y, ensemble_pred))

        except Exception as e:
            logger.error(
                "Ensemble evaluation failed",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )

        # Compare with the best individual model.
        if individual_metrics:
            best_model_name = max(
                individual_metrics.keys(),
                key=lambda k: list(individual_metrics[k].values())[0],
            )
            ensemble_metrics["best_individual_model"] = best_model_name

        return ensemble_metrics


# Factory for creating models.
def create_model(
    model_type: str,
    model_name: str,
    prediction_type: str,
    features: List[str],
    target: Optional[str] = None,
    model_params: Optional[Dict] = None,
    mlflow_manager: Optional[MLFlowManager] = None,
) -> MLPredictor:
    """Create an ML predictor."""

    if model_type.lower() in ["sklearn", "scikit-learn", "random_forest", "rf"]:
        model_class_map = {
            PredictionType.CLASSIFICATION: RandomForestClassifier,
            PredictionType.REGRESSION: RandomForestRegressor,
        }

        return SklearnPredictor(
            model_name=model_name,
            prediction_type=prediction_type,
            features=features,
            target=target,
            model_class=model_class_map.get(
                prediction_type, RandomForestClassifier),
            model_params=model_params,
            mlflow_manager=mlflow_manager,
        )

    elif model_type.lower() in ["tensorflow", "keras", "tf", "neural_network", "nn"]:
        # TensorFlow support removed - use sklearn fallback.
        logger.warning("TensorFlow models not supported, falling back to sklearn")
        return SklearnPredictor(
            model_name=model_name,
            prediction_type=prediction_type,
            features=features,
            target=target,
            model_params=model_params,
            mlflow_manager=mlflow_manager,
        )

    else:
        # Default fallback
        return SklearnPredictor(
            model_name=model_name,
            prediction_type=prediction_type,
            features=features,
            target=target,
            model_params=model_params,
            mlflow_manager=mlflow_manager,
        )
