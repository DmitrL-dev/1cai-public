from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MetricRecordRequest(BaseModel):
    """Request for recording metric."""

    metric_type: str
    assistant_role: str
    value: float
    project_id: str = Field(..., description="Project ID")
    user_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    feedback_score: Optional[float] = None


class ModelCreateRequest(BaseModel):
    """Request for creating model."""

    model_name: str
    model_type: str
    prediction_type: str
    features: List[str]
    target: Optional[str] = None
    hyperparameters: Optional[Dict[str, Any]] = None


class TrainingRequest(BaseModel):
    """Request for training model."""

    model_name: str
    model_type: str
    features: List[str]
    target: str
    training_data: List[Dict[str, Any]]
    training_type: str = "initial"
    test_size: float = 0.2
    hyperparameters: Optional[Dict[str, Any]] = None
    preprocessing_config: Optional[Dict[str, Any]] = None


class PredictionRequest(BaseModel):
    """Request for prediction."""

    model_name: str
    input_data: Dict[str, Any] = Field(..., description="Input data for prediction")


class ABTestCreateRequest(BaseModel):
    """Request for creating A/B test."""

    test_name: str
    description: str
    test_type: str
    control_model_name: str
    treatment_model_name: str
    traffic_split: float
    primary_metric: str
    success_criteria: Dict[str, float]
    duration_days: int
    min_sample_size: int
    significance_level: float = 0.05


class ABTestPredictionRequest(BaseModel):
    """Request for A/B test prediction."""

    test_id: str
    user_id: str
    session_id: str
    input_data: Dict[str, Any]
