"""
Celery tasks have been disabled in favor of NATS (Event-Driven Architecture).
See src/modules/revolutionary/README.md for details.
"""

# import os
# import sys
# from datetime import datetime, timedelta
# from typing import Any, Dict, List, Optional
#
# import numpy as np
# import pandas as pd
# # from celery import Celery, chord, group
# # from celery.schedules import crontab
# # from celery.utils.log import get_task_logger
#
# # Adjust path to include src
# # sys.path.append(os.path.dirname(os.path.dirname(
# #     os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
#
# # from src.config import settings
# # from src.ml.experiments.mlflow_manager import MLFlowManager
# # from src.ml.metrics.collector import MetricsCollector
# # from src.ml.training.trainer import ModelTrainer
#
# # Celery Configuration
# # celery_app = Celery(
# #     "ml_module_worker",
# #     broker=settings.CELERY_BROKER_URL,
# #     backend=settings.CELERY_RESULT_BACKEND,
# # )
#
# # ... (rest of the file is disabled)
