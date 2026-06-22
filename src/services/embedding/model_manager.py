import importlib
import os
import time
from typing import Any, Dict

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

try:
    pass

    EMBEDDINGS_AVAILABLE = True
except ImportError:
    logger.warning("sentence-transformers not installed.")
    EMBEDDINGS_AVAILABLE = False


class ModelManager:
    """
    Manages loading and access to SentenceTransformer models on CPU and GPU.
    """

    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, model_name: str = None, hybrid_mode: bool = None):
        self.model_name = model_name or self.DEFAULT_MODEL

        if hybrid_mode is None:
            hybrid_mode = os.getenv("EMBEDDING_HYBRID_MODE", "false").lower() == "true"
        self.hybrid_mode = hybrid_mode

        self.model_cpu = None
        self.model_gpu = None
        self.model = None  # Primary model

        self._multi_gpu_enabled = (
            os.getenv("EMBEDDING_MULTI_GPU_ENABLED", "false").lower() == "true"
        )
        self._gpu_devices = []
        self._gpu_models: Dict[int, Any] = {}

        self._init_gpu_devices()
        self.load_model()

    def _init_gpu_devices(self):
        # GPU disabled — torch removed, CPU-only for BSL analysis
        pass

    def load_model(self, max_retries: int = 3, retry_delay: float = 1.0):
        if not EMBEDDINGS_AVAILABLE:
            return

        # CPU-only (torch removed)
        self._load_single_model(max_retries, retry_delay, use_gpu=False)

    def _load_single_model(self, max_retries: int, retry_delay: float, use_gpu: bool):
        for attempt in range(max_retries):
            try:
                device = "cuda" if use_gpu else "cpu"
                logger.info(
                    f"Loading model {self.model_name} on {device} (attempt {attempt+1})"
                )

                module = importlib.import_module("sentence_transformers")
                transformer_cls = getattr(module, "SentenceTransformer")
                self.model = transformer_cls(self.model_name, device=device)

                if use_gpu:
                    self.model_gpu = self.model
                else:
                    self.model_cpu = self.model

                logger.info("Model loaded on %s", device)
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2**attempt))
                else:
                    logger.error("Failed to load model: %s", e)
                    self.model = None

    def _load_hybrid_models(self, max_retries: int, retry_delay: float):
        logger.info("Loading models in hybrid mode (CPU + GPU)")

        # GPU
        if self._multi_gpu_enabled and self._gpu_devices:
            for device_id in self._gpu_devices:
                try:
                    module = importlib.import_module("sentence_transformers")
                    transformer_cls = getattr(module, "SentenceTransformer")
                    model = transformer_cls(self.model_name, device=f"cuda:{device_id}")
                    self._gpu_models[device_id] = model
                except Exception as e:
                    logger.warning("Failed to load on GPU %s: {e}", device_id)

            if self._gpu_models:
                self.model_gpu = self._gpu_models[list(self._gpu_models.keys())[0]]
        else:
            try:
                module = importlib.import_module("sentence_transformers")
                transformer_cls = getattr(module, "SentenceTransformer")
                self.model_gpu = transformer_cls(self.model_name, device="cuda")
            except Exception as e:
                logger.warning("Failed to load GPU model: %s", e)

        # CPU
        try:
            module = importlib.import_module("sentence_transformers")
            transformer_cls = getattr(module, "SentenceTransformer")
            self.model_cpu = transformer_cls(self.model_name, device="cpu")
        except Exception as e:
            logger.warning("Failed to load CPU model: %s", e)

        self.model = self.model_gpu or self.model_cpu

    def get_model(self, device: str = "auto") -> Any:
        if device == "cpu":
            return self.model_cpu
        elif device == "gpu" or device == "cuda":
            return self.model_gpu
        return self.model

    def get_embedding_dimension(self) -> int:
        if self.model:
            return self.model.get_sentence_embedding_dimension()
        return 384
