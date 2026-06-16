import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse

from src.middleware.rate_limiter import limiter
from src.modules.ml.api.dependencies import get_ml_services, trained_models
from src.modules.ml.domain.models import (
    ABTestCreateRequest,
    MetricRecordRequest,
    ModelCreateRequest,
    PredictionRequest,
    TrainingRequest,
)
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

router = APIRouter(prefix="/api/v1/ml", tags=["Machine Learning"])


@router.get("/")
async def root():
    """Корневой эндпоинт ML модуля."""
    return {
        "message": "ML Continuous Improvement API",
        "version": "2.1.0",
        "status": "active",
        "services": [
            "metrics_collection",
            "model_training",
            "ab_testing",
            "predictions",
        ],
    }


@router.get("/health")
async def health_check(services=Depends(get_ml_services)):
    """Проверка здоровья ML системы."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {},
    }

    try:
        health_status["services"]["mlflow"] = {
            "status": "healthy",
            "tracking_uri": services["mlflow_manager"].tracking_uri,
        }
    except Exception as e:
        health_status["services"]["mlflow"] = {
            "status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"

    try:
        summary = await services["metrics_collector"].get_performance_summary(hours_back=1)
        health_status["services"]["metrics"] = {
            "status": "healthy",
            "metrics_collected": len(summary),
        }
    except Exception as e:
        health_status["services"]["metrics"] = {
            "status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"

    try:
        active_tests = len(services["ab_test_manager"].active_tests)
        health_status["services"]["ab_testing"] = {
            "status": "healthy",
            "active_tests": active_tests,
        }
    except Exception as e:
        health_status["services"]["ab_testing"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_status["status"] = "degraded"

    return JSONResponse(content=health_status)

# ===== МЕТРИКИ =====


@router.post("/metrics/record")
async def record_metric(
    request: MetricRecordRequest, services=Depends(get_ml_services)
):
    """Запись метрики эффективности."""
    try:
        from src.ml.metrics.collector import AssistantRole, MetricType

        try:
            metric_type = MetricType(request.metric_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid metric_type: {request.metric_type}",
            )

        try:
            assistant_role = AssistantRole(request.assistant_role.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid assistant_role: {request.assistant_role}",
            )

        metric_id = None
        collector = services["metrics_collector"]

        if metric_type == MetricType.REQUIREMENT_ANALYSIS_ACCURACY:
            metric_id = await collector.record_requirement_analysis_accuracy(
                assistant_role=assistant_role,
                predicted_requirements=request.context.get(
                    "predicted_requirements", []),
                actual_requirements=request.context.get(
                    "actual_requirements", []),
                project_id=request.project_id,
                context=request.context,
            )
        elif metric_type == MetricType.DIAGRAM_QUALITY_SCORE:
            metric_id = await collector.record_diagram_quality_score(
                assistant_role=assistant_role,
                generated_diagram=request.context.get("diagram", ""),
                user_feedback=request.feedback_score,
                project_id=request.project_id,
                context=request.context,
            )
        elif metric_type == MetricType.RISK_ASSESSMENT_PRECISION:
            metric_id = await collector.record_risk_assessment_precision(
                assistant_role=assistant_role,
                predicted_risks=request.context.get("predicted_risks", []),
                actual_risks=request.context.get("actual_risks", []),
                project_id=request.project_id,
                context=request.context,
            )
        elif metric_type == MetricType.RESPONSE_TIME:
            metric_id = await collector.record_response_time(
                assistant_role=assistant_role,
                response_time=request.value,
                project_id=request.project_id,
                context=request.context,
            )
        elif metric_type == MetricType.USER_SATISFACTION:
            metric_id = await collector.record_user_satisfaction(
                assistant_role=assistant_role,
                satisfaction_score=request.value,
                project_id=request.project_id,
                user_id=request.user_id,
                context=request.context,
            )
        else:
            raise ValueError(f"Неподдерживаемый тип метрики: {metric_type}")

        return {
            "status": "success",
            "metric_id": metric_id,
            "message": f"Метрика {metric_type.value} успешно записана",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error recording metric: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/summary")
async def get_metrics_summary(hours_back: int = 24, services=Depends(get_ml_services)):
    """Получение сводки метрик."""
    try:
        summary = await asyncio.wait_for(
            services["metrics_collector"].get_performance_summary(hours_back),
            timeout=30.0,
        )
        return {
            "status": "success",
            "hours_back": hours_back,
            "summary": summary,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504, detail="Timeout getting metrics summary")
    except Exception as e:
        logger.error("Error getting metrics summary: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ===== МОДЕЛИ =====


@router.post("/models/create")
@limiter.limit("5/minute")
async def create_model(request: ModelCreateRequest, services=Depends(get_ml_services)):
    """Создание модели ML."""
    try:
        from src.modules.ml.domain.predictor import create_model as create_model_impl

        model = create_model_impl(
            model_type=request.model_type,
            model_name=request.model_name,
            prediction_type=request.prediction_type,
            features=request.features,
            target=request.target,
            model_params=request.hyperparameters,
            mlflow_manager=services["mlflow_manager"],
        )

        trained_models[request.model_name] = model

        return {
            "status": "success",
            "model_name": request.model_name,
            "message": "Модель успешно создана",
        }
    except Exception as e:
        logger.error("Error creating model: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/models/train")
async def train_model(
    request: TrainingRequest,
    background_tasks: BackgroundTasks,
    services=Depends(get_ml_services),
):
    """Обучение модели."""
    try:
        import pandas as pd
        from src.modules.ml.application.trainer import TrainingType

        training_data_df = pd.DataFrame(request.training_data)
        training_type_enum = TrainingType(request.training_type.lower())

        job_id = services["model_trainer"].create_training_job(
            model_name=request.model_name,
            model_type=request.model_type,
            features=request.features,
            target=request.target,
            training_data=training_data_df,
            training_type=training_type_enum,
            hyperparameters=request.hyperparameters,
            preprocessing_config=request.preprocessing_config,
        )

        return {
            "status": "submitted",
            "job_id": job_id,
            "message": "Задача обучения поставлена в очередь",
        }
    except Exception as e:
        logger.error("Error training model: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/models/{model_name}/predict")
async def predict_model(
    model_name: str, request: PredictionRequest, services=Depends(get_ml_services)
):
    """Предсказание с помощью модели."""
    try:
        if model_name not in trained_models:
            raise ValueError(f"Модель {model_name} не найдена")

        model = trained_models[model_name]

        import pandas as pd
        input_df = pd.DataFrame([request.input_data])

        predictions = model.predict(input_df)
        explanation = model.explain_prediction(input_df)

        return {
            "status": "success",
            "model_name": model_name,
            "predictions": predictions.tolist() if hasattr(predictions, "tolist") else predictions,
            "explanation": explanation,
        }
    except Exception as e:
        logger.error("Error predicting: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/models")
async def list_models():
    """Список всех доступных моделей."""
    models_info = []
    for model_name, model in trained_models.items():
        info = {
            "model_name": model_name,
            "prediction_type": getattr(model, "prediction_type", "unknown"),
            "is_trained": getattr(model, "is_trained", False),
        }
        models_info.append(info)
    return {"status": "success", "models": models_info}

# ===== A/B ТЕСТИРОВАНИЕ =====


@router.post("/ab-tests/create")
@limiter.limit("3/minute")
async def create_ab_test(
    request: ABTestCreateRequest, services=Depends(get_ml_services)
):
    """Создание A/B теста."""
    try:
        if request.control_model_name not in trained_models:
            raise ValueError(
                f"Контрольная модель {request.control_model_name} не найдена")
        if request.treatment_model_name not in trained_models:
            raise ValueError(
                f"Treatment модель {request.treatment_model_name} не найдена")

        from src.ml.ab_testing.tester import ABTestConfig, TestType

        config = ABTestConfig(
            test_name=request.test_name,
            description=request.description,
            test_type=TestType(request.test_type.lower()),
            control_model=trained_models[request.control_model_name],
            treatment_model=trained_models[request.treatment_model_name],
            traffic_split=request.traffic_split,
            primary_metric=request.primary_metric,
            success_criteria=request.success_criteria,
            duration_days=request.duration_days,
            min_sample_size=request.min_sample_size,
            significance_level=request.significance_level,
        )

        test_id = services["ab_test_manager"].create_ab_test(config)

        return {
            "status": "success",
            "test_id": test_id,
            "message": "A/B тест успешно создан",
        }
    except Exception as e:
        logger.error("Error creating AB test: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
