import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Union

from src.config import USE_NESTED_LEARNING
from src.resilience.error_recovery import CircuitState
from src.utils.structured_logging import StructuredLogger

from .cache_manager import CacheManager
from .model_manager import ModelManager
from .resource_manager import ResourceManager

logger = StructuredLogger(__name__).logger


class EmbeddingService:
    """
    Refactored EmbeddingService using composition.

    With Nested Learning support for continual learning (optional).
    """

    def __init__(
        self, model_name: str = None, hybrid_mode: bool = None, redis_client=None
    ):
        self.model_manager = ModelManager(model_name, hybrid_mode)
        self.cache_manager = CacheManager(redis_client)
        self.resource_manager = ResourceManager()

        self.hybrid_mode = self.model_manager.hybrid_mode
        self._executor = ThreadPoolExecutor(max_workers=2) if self.hybrid_mode else None

        # Nested Learning integration (optional)
        self._nested = None
        if USE_NESTED_LEARNING:
            try:
                from .nested_service import NestedEmbeddingService

                self._nested = NestedEmbeddingService(self)
                logger.info("Nested Learning enabled for EmbeddingService")
            except Exception as e:
                logger.warning(
                    f"Failed to initialize Nested Learning: {e}", exc_info=True
                )

    @property
    def model(self):
        """Expose the underlying model for tests"""
        return self.model_manager.get_model()

    def encode(
        self,
        text: Union[str, List[str]],
        batch_size: int = 32,
        show_progress: bool = False,
        use_device: Optional[str] = None,
    ) -> Union[List[float], List[List[float]]]:
        # Use nested encoding if enabled and text is string
        if self._nested and isinstance(text, str):
            try:
                return self._nested.encode(text, context={}).tolist()
            except Exception as e:
                logger.warning(
                    "Nested encoding failed, falling back to standard: %s", e
                )

        if text is None:
            return []

        if isinstance(text, list):
            # Filter None values and empty strings
            text = [t for t in text if t and isinstance(t, str) and t.strip()]
            if not text:
                return []
            # Truncate list if too long
            if len(text) > 1000:
                text = text[:1000]

            # Truncate items if too long
            text = [t[:100000] for t in text]

        if not text:
            return [] if isinstance(text, list) else []

        # Check cache
        cache_key = self.cache_manager.get_cache_key(text)
        cached = self.cache_manager.get(cache_key)
        if cached:
            self.resource_manager.update_stats("cache", cache_hit=True)
            return cached

        # Check semantic cache (only for single string)
        if isinstance(text, str):
            # We need a way to get embedding for query to check semantic cache
            # This creates a circular dependency if we use self.encode inside cache manager
            # So we pass a lambda that uses a lightweight check or the model directly
            def get_query_embedding(t):
                # Use CPU model for quick check if available
                model = self.model_manager.get_model(
                    "cpu"
                ) or self.model_manager.get_model("gpu")
                if model:
                    return model.encode([t], show_progress_bar=False)[0].tolist()
                return None

            semantic_cached = self.cache_manager.get_from_semantic_cache(
                text, get_query_embedding
            )
            if semantic_cached:
                self.resource_manager.update_stats("cache", cache_hit=True)
                return semantic_cached

        self.resource_manager.update_stats("cache", cache_hit=False)

        # Encode
        result = []
        if self.hybrid_mode and isinstance(text, list) and len(text) > 1:
            result = self._encode_hybrid(text, batch_size, show_progress)
        else:
            result = self._encode_single(text, batch_size, show_progress, use_device)

        # Save to cache
        if result:
            self.cache_manager.set(cache_key, result)
            if isinstance(text, str):
                # Normalize for semantic cache
                emb = (
                    result[0]
                    if isinstance(result, list) and isinstance(result[0], list)
                    else result
                )
                self.cache_manager.save_to_semantic_cache(text, emb)

        return result

    def _encode_single(self, text, batch_size, show_progress, use_device):
        device = use_device or ("gpu" if self.model_manager.model_gpu else "cpu")
        model = self.model_manager.get_model(device)

        if not model:
            # Fallback
            model = self.model_manager.get_model()
            if not model:
                return []

        cb = self.resource_manager.get_circuit_breaker(device)

        try:
            if cb.state == CircuitState.OPEN:
                # Fallback to other device
                other_device = "cpu" if device == "gpu" else "gpu"
                logger.warning(
                    f"Circuit breaker OPEN for {device}, falling back to {other_device}"
                )
                return self._encode_single(
                    text, batch_size, show_progress, other_device
                )

            start = time.time()
            embeddings = model.encode(
                text,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
            )
            duration = time.time() - start

            # Update stats
            count = len(text) if isinstance(text, list) else 1
            self.resource_manager.update_performance(device, duration, count)
            self.resource_manager.update_stats(
                device, tokens=len(str(text))
            )  # Approx tokens

            if isinstance(text, str):
                return embeddings.tolist()
            return [emb.tolist() for emb in embeddings]

        except Exception as e:
            cb.record_failure()
            logger.error("Encoding error on %s: {e}", device)
            return []

    def _encode_hybrid(
        self, text: List[str], batch_size: int, show_progress: bool
    ) -> List[List[float]]:
        # Simple split for now
        mid = len(text) // 2
        batch_cpu = text[:mid]
        batch_gpu = text[mid:]

        results = [None] * len(text)

        with self._executor:
            futures = {}
            if batch_cpu:
                futures[
                    self._executor.submit(
                        self._encode_single, batch_cpu, batch_size, show_progress, "cpu"
                    )
                ] = (
                    0,
                    "cpu",
                )
            if batch_gpu:
                futures[
                    self._executor.submit(
                        self._encode_single, batch_gpu, batch_size, show_progress, "gpu"
                    )
                ] = (
                    mid,
                    "gpu",
                )

            for future in as_completed(futures):
                start_idx, device = futures[future]
                try:
                    res = future.result()
                    results[start_idx : start_idx + len(res)] = res
                except Exception as e:
                    logger.error("Hybrid encoding error on %s: {e}", device)

        return results

    async def generate_embedding(
        self, text: Union[str, List[str]]
    ) -> Union[List[float], List[List[float]]]:
        return self.encode(text)

    def encode_code(self, code: str) -> List[float]:
        # Simple preprocessing
        clean_code = "\n".join(
            [
                line.strip()
                for line in code.split("\n")
                if line.strip() and not line.strip().startswith("//")
            ]
        )
        return self.encode(clean_code[:5000])

    def encode_function(self, func_data: Dict) -> List[float]:
        parts = [func_data.get("name", ""), func_data.get("description", "")]
        return self.encode(" ".join(parts))

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "stats": self.resource_manager.get_stats(),
            "cache": self.cache_manager.get_stats(),
        }
