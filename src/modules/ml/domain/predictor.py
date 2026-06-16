# [NEXUS IDENTITY] ID: 3135880199165626437 | DATE: 2025-11-19

"""
Р‘Р°Р·РѕРІС‹Р№ РєР»Р°СЃСЃ РґР»СЏ ML РјРѕРґРµР»РµР№ РїСЂРµРґСЃРєР°Р·Р°РЅРёСЏ.
РРЅС‚РµРіСЂР°С†РёСЏ СЃ TensorFlow/PyTorch Рё scikit-learn РґР»СЏ СЂР°Р·Р»РёС‡РЅС‹С… С‚РёРїРѕРІ РјРѕРґРµР»РµР№.
"""

import pickle
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

# ML РјРѕРґРµР»Рё
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
    """РўРёРїС‹ РїСЂРµРґСЃРєР°Р·Р°РЅРёР№"""

    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    RECOMMENDATION = "recommendation"


class MLPredictor(ABC):
    """РђР±СЃС‚СЂР°РєС‚РЅС‹Р№ Р±Р°Р·РѕРІС‹Р№ РєР»Р°СЃСЃ РґР»СЏ РІСЃРµС… ML РјРѕРґРµР»РµР№"""

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

        # РљРѕРЅС„РёРіСѓСЂР°С†РёСЏ РјРѕРґРµР»Рё
        self.config = {
            "model_name": model_name,
            "prediction_type": prediction_type,
            "features": features,
            "target": target,
            "created_at": datetime.utcnow().isoformat(),
        }

        logger.info("РРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ MLPredictor",
                    extra={"model_name": model_name})

    @abstractmethod
    def fit(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Optional[Union[pd.Series, np.ndarray]] = None,
    ) -> "MLPredictor":
        """РћР±СѓС‡РµРЅРёРµ РјРѕРґРµР»Рё"""

    @abstractmethod
    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[np.ndarray, pd.DataFrame]:
        """РџСЂРµРґСЃРєР°Р·Р°РЅРёРµ"""

    @abstractmethod
    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> Optional[np.ndarray]:
        """РџСЂРµРґСЃРєР°Р·Р°РЅРёРµ РІРµСЂРѕСЏС‚РЅРѕСЃС‚РµР№ (РґР»СЏ РєР»Р°СЃСЃРёС„РёРєР°С†РёРё)"""

    def save_model(self, filepath: str):
        """РЎРѕС…СЂР°РЅРµРЅРёРµ РјРѕРґРµР»Рё"""
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
                "РњРѕРґРµР»СЊ СЃРѕС…СЂР°РЅРµРЅР°",
                extra={"model_name": self.model_name, "filepath": filepath},
            )

        except Exception as e:
            logger.error(
                "РћС€РёР±РєР° СЃРѕС…СЂР°РЅРµРЅРёСЏ РјРѕРґРµР»Рё",
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
        """Р—Р°РіСЂСѓР·РєР° РјРѕРґРµР»Рё"""
        try:
            with open(filepath, "rb") as f:
                model_data = pickle.load(f)

            self.config = model_data["config"]
            self.model = model_data["model"]
            self.is_trained = model_data["is_trained"]
            self.features = model_data["features"]
            self.target = model_data["target"]

            logger.info(
                "РњРѕРґРµР»СЊ Р·Р°РіСЂСѓР¶РµРЅР°",
                extra={"model_name": self.model_name, "filepath": filepath},
            )

        except Exception as e:
            logger.error(
                "РћС€РёР±РєР° Р·Р°РіСЂСѓР·РєРё РјРѕРґРµР»Рё",
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
        """РћС†РµРЅРєР° РјРѕРґРµР»Рё"""

        if not self.is_trained:
            raise ValueError("РњРѕРґРµР»СЊ РЅРµ РѕР±СѓС‡РµРЅР°")

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

        logger.info("РћС†РµРЅРєР° РјРѕРґРµР»Рё", extra={
                    "model_name": self.model_name, "metrics": metrics})

        return metrics

    def log_model_metrics_to_mlflow(self, metrics: Dict[str, float], run_id: Optional[str] = None):
        """Р›РѕРіРёСЂРѕРІР°РЅРёРµ РјРµС‚СЂРёРє РІ MLflow"""

        if self.mlflow_manager:
            self.mlflow_manager.log_metrics(metrics)

    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """РџРѕР»СѓС‡РµРЅРёРµ РІР°Р¶РЅРѕСЃС‚Рё РїСЂРёР·РЅР°РєРѕРІ (РµСЃР»Рё РїРѕРґРґРµСЂР¶РёРІР°РµС‚СЃСЏ)"""

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
        """РћР±СЉСЏСЃРЅРµРЅРёРµ РїСЂРµРґСЃРєР°Р·Р°РЅРёСЏ"""

        if not self.is_trained:
            raise ValueError("РњРѕРґРµР»СЊ РЅРµ РѕР±СѓС‡РµРЅР°")

        if isinstance(X, pd.DataFrame):
            sample = X.iloc[index].to_dict()
        else:
            sample = dict(zip(self.features, X[index]))

        # Р‘Р°Р·РѕРІР°СЏ РёРЅС‚РµСЂРїСЂРµС‚Р°С†РёСЏ РЅР° РѕСЃРЅРѕРІРµ РІР°Р¶РЅРѕСЃС‚Рё РїСЂРёР·РЅР°РєРѕРІ
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
            # РўРѕРї-5 С„РёС‡
            explanation["contributing_features"] = sorted_features[:5]

        return explanation


class SklearnPredictor(MLPredictor):
    """Р РµР°Р»РёР·Р°С†РёСЏ РїСЂРµРґРёРєС‚РѕСЂР° РЅР° РѕСЃРЅРѕРІРµ scikit-learn"""

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
            "РРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ SklearnPredictor",
            extra={"model_name": model_name,
                   "model_class": self.model_class.__name__},
        )

    def _get_default_model_class(self, prediction_type: str) -> type:
        """РџРѕР»СѓС‡РµРЅРёРµ РєР»Р°СЃСЃР° РјРѕРґРµР»Рё РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ"""

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
        """РћР±СѓС‡РµРЅРёРµ РјРѕРґРµР»Рё"""

        try:
            # РџСЂРµРѕР±СЂР°Р·РѕРІР°РЅРёРµ РґР°РЅРЅС‹С…
            if isinstance(X, pd.DataFrame):
                X_processed = X[self.features].fillna(0)
            else:
                X_processed = pd.DataFrame(X, columns=self.features).fillna(0)

            # РЎРѕР·РґР°РЅРёРµ Рё РѕР±СѓС‡РµРЅРёРµ РјРѕРґРµР»Рё
            self.model = self.model_class(**self.model_params)
            self.model.fit(X_processed, y)

            self.is_trained = True

            logger.info(
                "РњРѕРґРµР»СЊ РѕР±СѓС‡РµРЅР°",
                extra={
                    "model_name": self.model_name,
                    "samples_count": len(X_processed),
                },
            )

            return self

        except Exception as e:
            logger.error(
                "РћС€РёР±РєР° РѕР±СѓС‡РµРЅРёСЏ РјРѕРґРµР»Рё",
                extra={
                    "model_name": self.model_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[np.ndarray, pd.DataFrame]:
        """РџСЂРµРґСЃРєР°Р·Р°РЅРёРµ"""

        if not self.is_trained:
            raise ValueError("РњРѕРґРµР»СЊ РЅРµ РѕР±СѓС‡РµРЅР°")

        try:
            # РџСЂРµРѕР±СЂР°Р·РѕРІР°РЅРёРµ РґР°РЅРЅС‹С…
            if isinstance(X, pd.DataFrame):
                X_processed = X[self.features].fillna(0)
            else:
                X_processed = pd.DataFrame(X, columns=self.features).fillna(0)

            predictions = self.model.predict(X_processed)

            logger.debug("Р’С‹РїРѕР»РЅРµРЅРѕ РїСЂРµРґСЃРєР°Р·Р°РЅРёРµ", extra={
                         "samples_count": len(X_processed)})

            return predictions

        except Exception as e:
            logger.error(
                "РћС€РёР±РєР° РїСЂРµРґСЃРєР°Р·Р°РЅРёСЏ",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            raise

    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> Optional[np.ndarray]:
        """РџСЂРµРґСЃРєР°Р·Р°РЅРёРµ РІРµСЂРѕСЏС‚РЅРѕСЃС‚РµР№"""

        if not self.is_trained or not hasattr(self.model, "predict_proba"):
            return None

        try:
            # РџСЂРµРѕР±СЂР°Р·РѕРІР°РЅРёРµ РґР°РЅРЅС‹С…
            if isinstance(X, pd.DataFrame):
                X_processed = X[self.features].fillna(0)
            else:
                X_processed = pd.DataFrame(X, columns=self.features).fillna(0)

            probabilities = self.model.predict_proba(X_processed)

            logger.debug("Р’С‹С‡РёСЃР»РµРЅС‹ РІРµСЂРѕСЏС‚РЅРѕСЃС‚Рё", extra={
                         "samples_count": len(X_processed)})

            return probabilities

        except Exception as e:
            logger.error(
                "РћС€РёР±РєР° РІС‹С‡РёСЃР»РµРЅРёСЏ РІРµСЂРѕСЏС‚РЅРѕСЃС‚РµР№",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return None


# TensorFlowPredictor removed вЂ” tensorflow was never in requirements.txt
# 230 lines of dead code deleted. Use SklearnPredictor instead.
#
# To restore: git checkout v4.0-pre-cleanup -- src/modules/ml/domain/predictor.py

class ModelEnsemble:
    """Ансамбль ML моделей для улучшения предсказаний"""

    def __init__(self, models: List[MLPredictor], ensemble_method: str = "average"):
        self.models = models
        self.ensemble_method = ensemble_method

        logger.info(
            "РЎРѕР·РґР°РЅ Р°РЅСЃР°РјР±Р»СЊ РјРѕРґРµР»РµР№",
            extra={"models_count": len(
                models), "ensemble_method": ensemble_method},
        )

    def fit(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Optional[Union[pd.Series, np.ndarray]] = None,
    ) -> "ModelEnsemble":
        """РћР±СѓС‡РµРЅРёРµ РІСЃРµС… РјРѕРґРµР»РµР№ РІ Р°РЅСЃР°РјР±Р»Рµ"""

        for model in self.models:
            model.fit(X, y)

        logger.info("Р’СЃРµ РјРѕРґРµР»Рё РІ Р°РЅСЃР°РјР±Р»Рµ РѕР±СѓС‡РµРЅС‹")
        return self

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[np.ndarray, pd.DataFrame]:
        """РџСЂРµРґСЃРєР°Р·Р°РЅРёРµ Р°РЅСЃР°РјР±Р»СЏ"""

        predictions = []

        for model in self.models:
            pred = model.predict(X)
            predictions.append(pred)

        # РћР±СЉРµРґРёРЅРµРЅРёРµ РїСЂРµРґСЃРєР°Р·Р°РЅРёР№
        if self.ensemble_method == "average":
            ensemble_pred = np.mean(predictions, axis=0)
        elif self.ensemble_method == "majority_vote":
            # Р”Р»СЏ РєР»Р°СЃСЃРёС„РёРєР°С†РёРё - РіРѕР»РѕСЃРѕРІР°РЅРёРµ Р±РѕР»СЊС€РёРЅСЃС‚РІРѕРј
            if self.models[0].prediction_type == PredictionType.CLASSIFICATION:
                ensemble_pred = np.round(np.mean(predictions, axis=0))
            else:
                ensemble_pred = np.mean(predictions, axis=0)
        else:
            ensemble_pred = predictions[0]  # Fallback

        return ensemble_pred

    def predict_with_uncertainty(self, X: Union[pd.DataFrame, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        """РџСЂРµРґСЃРєР°Р·Р°РЅРёРµ СЃ РѕС†РµРЅРєРѕР№ РЅРµРѕРїСЂРµРґРµР»РµРЅРЅРѕСЃС‚Рё"""

        predictions = []

        for model in self.models:
            pred = model.predict(X)
            predictions.append(pred)

        predictions = np.array(predictions)

        # РЎСЂРµРґРЅРµРµ РїСЂРµРґСЃРєР°Р·Р°РЅРёРµ
        mean_pred = np.mean(predictions, axis=0)

        # РЎС‚Р°РЅРґР°СЂС‚РЅРѕРµ РѕС‚РєР»РѕРЅРµРЅРёРµ (РєР°Рє РјРµСЂР° РЅРµРѕРїСЂРµРґРµР»РµРЅРЅРѕСЃС‚Рё)
        uncertainty = np.std(predictions, axis=0)

        return mean_pred, uncertainty

    def evaluate_ensemble(
        self, X: Union[pd.DataFrame, np.ndarray], y: Union[pd.Series, np.ndarray]
    ) -> Dict[str, float]:
        """РћС†РµРЅРєР° Р°РЅСЃР°РјР±Р»СЏ"""

        ensemble_metrics = {}
        individual_metrics = {}

        # РћС†РµРЅРєР° РѕС‚РґРµР»СЊРЅС‹С… РјРѕРґРµР»РµР№
        for i, model in enumerate(self.models):
            try:
                metrics = model.evaluate(X, y)
                individual_metrics[f"model_{i}"] = metrics
            except Exception as e:
                logger.warning(
                    "РћС€РёР±РєР° РѕС†РµРЅРєРё РјРѕРґРµР»Рё",
                    extra={
                        "model_index": i,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )

        # РћС†РµРЅРєР° Р°РЅСЃР°РјР±Р»СЏ
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
                "РћС€РёР±РєР° РѕС†РµРЅРєРё Р°РЅСЃР°РјР±Р»СЏ",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )

        # РЎСЂР°РІРЅРµРЅРёРµ СЃ Р»СѓС‡С€РµР№ РёРЅРґРёРІРёРґСѓР°Р»СЊРЅРѕР№ РјРѕРґРµР»СЊСЋ
        if individual_metrics:
            best_model_name = max(
                individual_metrics.keys(),
                key=lambda k: list(individual_metrics[k].values())[0],
            )
            ensemble_metrics["best_individual_model"] = best_model_name

        return ensemble_metrics


# Р¤Р°Р±СЂРёРєР° РґР»СЏ СЃРѕР·РґР°РЅРёСЏ РјРѕРґРµР»РµР№
def create_model(
    model_type: str,
    model_name: str,
    prediction_type: str,
    features: List[str],
    target: Optional[str] = None,
    model_params: Optional[Dict] = None,
    mlflow_manager: Optional[MLFlowManager] = None,
) -> MLPredictor:
    """Р¤Р°Р±СЂРёРєР° РґР»СЏ СЃРѕР·РґР°РЅРёСЏ ML РјРѕРґРµР»РµР№"""

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
        # TensorFlow support removed вЂ” use sklearn fallback
        logger.warning(
            "TensorFlow models not supported, falling back to sklearn")
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
