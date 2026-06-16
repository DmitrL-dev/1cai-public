import hashlib
import json
import os
from collections import OrderedDict
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Dict, List, Optional, Union

import numpy as np

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class CacheManager:
    """
    Manages L1 (Memory) and L2 (Redis) caching for embeddings.
    Also handles quantization/dequantization.
    """

    def __init__(
        self,
        redis_client=None,
        quantization_enabled: bool = False,
        quantization_dtype: str = "int8",
    ):
        self._cache_enabled = (
            os.getenv("EMBEDDING_CACHE_ENABLED", "true").lower() == "true"
        )
        self._cache_max_size = int(os.getenv("EMBEDDING_CACHE_SIZE", "1000"))
        self._cache_ttl_seconds = int(os.getenv("EMBEDDING_CACHE_TTL", "3600"))

        # L1: In-memory LRU cache
        self._result_cache: OrderedDict[str, Dict] = OrderedDict()
        self._cache_lock = Lock()

        # L2: Redis cache
        self._redis_client = redis_client
        self._redis_enabled = redis_client is not None
        if self._redis_enabled:
            try:
                self._redis_client.ping()
                logger.info("Redis cache (L2) enabled for embeddings")
            except Exception as e:
                logger.warning("Redis connection failed, L2 cache disabled: %s", e)
                self._redis_enabled = False
                self._redis_client = None

        # Quantization
        self._quantization_enabled = quantization_enabled
        self._quantization_dtype = quantization_dtype

        # Semantic Cache
        self._semantic_cache_enabled = (
            os.getenv("EMBEDDING_SEMANTIC_CACHE", "true").lower() == "true"
        )
        self._semantic_similarity_threshold = float(
            os.getenv("EMBEDDING_SEMANTIC_THRESHOLD", "0.95")
        )
        self._semantic_cache: Dict[str, List[float]] = {}  # text_hash -> embedding

        # Advanced components (placeholders for now, injected via setters if needed)
        self._adaptive_quantizer = None
        self._semantic_cache_ann = None
        self._semantic_cache_ann_type = os.getenv(
            "EMBEDDING_SEMANTIC_CACHE_ANN_TYPE", "linear"
        )

    def get_cache_key(self, text: Union[str, List[str]]) -> str:
        if isinstance(text, str):
            text_str = text
        else:
            text_str = "|".join(text)
        return hashlib.sha256(text_str.encode()).hexdigest()

    def get(self, cache_key: str) -> Optional[Union[List[float], List[List[float]]]]:
        if not self._cache_enabled:
            return None

        # L1
        with self._cache_lock:
            if cache_key in self._result_cache:
                entry = self._result_cache[cache_key]
                if entry["expires_at"] > datetime.utcnow():
                    self._result_cache.move_to_end(cache_key)
                    value = entry["value"]
                    if self._quantization_enabled:
                        value = self._dequantize_embedding(value)
                    return value
                else:
                    del self._result_cache[cache_key]

        # L2
        if self._redis_enabled and self._redis_client:
            try:
                redis_key = f"embedding:{cache_key}"
                cached_value = self._redis_client.get(redis_key)
                if cached_value:
                    value = json.loads(cached_value)
                    if self._quantization_enabled:
                        value = self._dequantize_embedding(value)

                    # Promote to L1
                    with self._cache_lock:
                        expires_at = datetime.utcnow() + timedelta(
                            seconds=self._cache_ttl_seconds
                        )
                        self._result_cache[cache_key] = {
                            "value": value,
                            "created_at": datetime.utcnow(),
                            "expires_at": expires_at,
                        }
                        self._result_cache.move_to_end(cache_key)
                    return value
            except Exception as e:
                logger.debug("Redis cache error: %s", e)

        return None

    def set(self, cache_key: str, value: Union[List[float], List[List[float]]]):
        if not self._cache_enabled:
            return

        cache_value = value
        if self._quantization_enabled:
            cache_value = self._quantize_embedding(value)

        # L1
        with self._cache_lock:
            if (
                len(self._result_cache) >= self._cache_max_size
                and cache_key not in self._result_cache
            ):
                oldest_key = next(iter(self._result_cache))
                del self._result_cache[oldest_key]

            expires_at = datetime.utcnow() + timedelta(seconds=self._cache_ttl_seconds)
            self._result_cache[cache_key] = {
                "value": cache_value,
                "created_at": datetime.utcnow(),
                "expires_at": expires_at,
            }
            self._result_cache.move_to_end(cache_key)

        # L2
        if self._redis_enabled and self._redis_client:
            try:
                redis_key = f"embedding:{cache_key}"
                serialized = json.dumps(cache_value)
                self._redis_client.setex(redis_key, self._cache_ttl_seconds, serialized)
            except Exception as e:
                logger.debug("Error saving to Redis cache: %s", e)

    def get_from_semantic_cache(
        self, text: str, query_embedding_func
    ) -> Optional[List[float]]:
        """
        Try to find semantically similar text in cache.
        query_embedding_func: function that returns embedding for text (to compare with cache)
        """
        if not self._semantic_cache_enabled:
            return None

        # ANN lookup if available
        if self._semantic_cache_ann:
            try:
                query_embedding = query_embedding_func(text)
                if query_embedding is None:
                    return None

                result = self._semantic_cache_ann.search(
                    query_embedding, k=1, threshold=self._semantic_similarity_threshold
                )
                if result:
                    best_embedding, similarity, _ = result
                    logger.debug(f"Semantic cache ANN hit: {similarity:.3f}")
                    return best_embedding
            except Exception as e:
                logger.warning("Error in semantic cache ANN lookup: %s", e)

        # Linear lookup
        if not self._semantic_cache:
            return None

        try:
            query_embedding = query_embedding_func(text)
            if query_embedding is None:
                return None

            best_similarity = 0.0
            best_embedding = None

            for cached_embedding in self._semantic_cache.values():
                similarity = self._cosine_similarity(query_embedding, cached_embedding)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_embedding = cached_embedding

            if best_similarity >= self._semantic_similarity_threshold:
                logger.debug(f"Semantic cache hit: {best_similarity:.3f}")
                return best_embedding

        except Exception as e:
            logger.warning("Error in semantic cache lookup: %s", e)

        return None

    def save_to_semantic_cache(
        self, text: str, embedding: Union[List[float], List[List[float]]]
    ):
        if not self._semantic_cache_enabled:
            return

        try:
            max_size = int(os.getenv("EMBEDDING_SEMANTIC_CACHE_SIZE", "500"))

            # Normalize
            if (
                isinstance(embedding, list)
                and len(embedding) > 0
                and isinstance(embedding[0], list)
            ):
                embedding = embedding[0]

            if len(self._semantic_cache) >= max_size:
                oldest_key = next(iter(self._semantic_cache))
                del self._semantic_cache[oldest_key]

            text_hash = hashlib.md5(text.encode()).hexdigest()
            self._semantic_cache[text_hash] = embedding

            if self._semantic_cache_ann:
                self._semantic_cache_ann.add(embedding, text)

        except Exception as e:
            logger.warning("Error saving to semantic cache: %s", e)

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        try:
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return float(dot_product / (norm1 * norm2))
        except Exception:
            return 0.0

    def _quantize_embedding(self, embedding):
        if self._adaptive_quantizer:
            # Use adaptive if available
            try:
                if (
                    isinstance(embedding, list)
                    and len(embedding) > 0
                    and isinstance(embedding[0], list)
                ):
                    return [
                        self._adaptive_quantizer.quantize(emb)[0] for emb in embedding
                    ]
                else:
                    return self._adaptive_quantizer.quantize(embedding)[0]
            except Exception:
                pass

        # Simple quantization fallback
        try:
            if isinstance(embedding, list) and len(embedding) > 0:
                if isinstance(embedding[0], list):
                    return [self._quantize_embedding(emb) for emb in embedding]
                else:
                    arr = np.array(embedding, dtype=np.float32)
                    if self._quantization_dtype == "int8":
                        max_val = np.max(np.abs(arr))
                        scale = 127.0 / max_val if max_val > 0 else 1.0
                        return (arr * scale).astype(np.int8).tolist()
                    elif self._quantization_dtype == "int16":
                        max_val = np.max(np.abs(arr))
                        scale = 32767.0 / max_val if max_val > 0 else 1.0
                        return (arr * scale).astype(np.int16).tolist()
            return embedding
        except Exception:
            return embedding

    def _dequantize_embedding(self, quantized):
        try:
            if isinstance(quantized, list) and len(quantized) > 0:
                if isinstance(quantized[0], list):
                    return [self._dequantize_embedding(emb) for emb in quantized]
                else:
                    dtype = np.int8 if self._quantization_dtype == "int8" else np.int16
                    arr = np.array(quantized, dtype=dtype)
                    scale = (
                        1.0 / 127.0
                        if self._quantization_dtype == "int8"
                        else 1.0 / 32767.0
                    )
                    return (arr.astype(np.float32) * scale).tolist()
            return quantized
        except Exception:
            return quantized

    def get_stats(self) -> Dict[str, Any]:
        with self._cache_lock:
            return {
                "size": len(self._result_cache),
                "max_size": self._cache_max_size,
                "ttl_seconds": self._cache_ttl_seconds,
                "enabled": self._cache_enabled,
                "semantic_cache_size": len(self._semantic_cache),
            }
