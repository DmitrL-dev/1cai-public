"""
OCR Service for 1C Documents
Версия: 2.2.0
Refactored: Non-blocking execution for CPU/GPU intensive tasks
"""

import asyncio
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import settings
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class OCRProvider(str, Enum):
    """Провайдеры OCR"""

    DEEPSEEK = "deepseek"  # DeepSeek-OCR (primary, best accuracy 91%+)
    CHANDRA_HF = "chandra_hf"  # Chandra with HuggingFace (fallback)
    CHANDRA_VLLM = "chandra_vllm"  # Chandra with vLLM (faster)
    TESSERACT = "tesseract"  # Fallback для простых случаев


class DocumentType(str, Enum):
    """Типы документов 1С"""

    AUTO = "auto"  # Автоопределение
    CONTRACT = "contract"  # Договор
    ACT = "act"  # Акт
    INVOICE = "invoice"  # Счет
    WAYBILL = "waybill"  # Накладная
    FORM = "form"  # Бланк/форма
    TABLE = "table"  # Таблица
    OTHER = "other"


class OCRResult:
    """Результат OCR распознавания"""

    def __init__(
        self,
        text: str,
        confidence: float = 0.0,
        document_type: DocumentType = DocumentType.OTHER,
        metadata: Optional[Dict] = None,
        structured_data: Optional[Dict] = None,
    ):
        self.text = text
        self.confidence = confidence
        self.document_type = document_type
        self.metadata = metadata or {}
        self.structured_data = structured_data or {}
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь"""
        return {
            "text": self.text,
            "confidence": self.confidence,
            "document_type": self.document_type.value,
            "metadata": self.metadata,
            "structured_data": self.structured_data,
            "timestamp": self.timestamp.isoformat(),
        }


class OCRService:
    """Сервис OCR для документов 1С"""

    def __init__(
        self,
        provider: OCRProvider = OCRProvider.DEEPSEEK,
        enable_ai_parsing: bool = True,
        enable_fallback: bool = True,
    ):
        self.provider = provider
        self.enable_ai_parsing = enable_ai_parsing
        self.enable_fallback = enable_fallback
        self._executor = ThreadPoolExecutor(max_workers=2)

        # Инициализация провайдера
        if provider == OCRProvider.DEEPSEEK:
            self._init_deepseek()
        elif provider == OCRProvider.CHANDRA_HF or provider == OCRProvider.CHANDRA_VLLM:
            self._init_chandra()
        elif provider == OCRProvider.TESSERACT:
            self._init_tesseract()

        # Инициализация fallback провайдеров (если включен)
        if enable_fallback:
            self._init_fallback_providers()

    def _init_deepseek(self):
        """Инициализация DeepSeek-OCR с retry logic"""
        max_retries = 3
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
                import torch
                from transformers import AutoModel, AutoTokenizer

                logger.info(
                    f"Loading DeepSeek-OCR model (attempt {attempt + 1}/{max_retries})..."
                )

                model_name = "deepseek-ai/DeepSeek-OCR"

                self.deepseek_tokenizer = AutoTokenizer.from_pretrained(
                    model_name, trust_remote_code=True
                )
                self.deepseek_model = AutoModel.from_pretrained(
                    model_name,
                    device_map="auto",
                    torch_dtype=(
                        torch.float16 if torch.cuda.is_available() else torch.float32
                    ),
                    trust_remote_code=True,
                )

                self.deepseek_available = True
                self.deepseek_device = "cuda" if torch.cuda.is_available() else "cpu"

                logger.info(f"✓ DeepSeek-OCR initialized on {self.deepseek_device}")
                return

            except ImportError as e:
                logger.error("DeepSeek-OCR dependencies not installed: %s", e)
                self.deepseek_available = False
                raise
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error("Failed to initialize DeepSeek-OCR: %s", e)
                    self.deepseek_available = False
                    raise

                import time

                time.sleep(base_delay * (2**attempt))

    def _init_chandra(self):
        try:
            pass

            self.chandra_available = True
            logger.info("Chandra OCR initialized (fallback)")
        except ImportError:
            logger.warning("Chandra OCR not installed.")
            self.chandra_available = False

    def _init_tesseract(self):
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            self.tesseract_available = True
            logger.info("Tesseract OCR initialized (fallback)")
        except Exception as e:
            logger.warning("Tesseract not available: %s", e)
            self.tesseract_available = False

    def _init_fallback_providers(self):
        if self.provider != OCRProvider.CHANDRA_HF:
            try:
                self._init_chandra()
            except Exception:
                pass

        if self.provider != OCRProvider.TESSERACT:
            try:
                self._init_tesseract()
            except Exception:
                pass

    async def process_image(
        self,
        image_path: str,
        document_type: DocumentType = DocumentType.AUTO,
        max_retries: int = 3,
        timeout: float = 60.0,
        **kwargs,
    ) -> OCRResult:
        if not image_path or not isinstance(image_path, str):
            raise ValueError("image_path must be a non-empty string")

        image_path = os.path.normpath(image_path)
        if not os.path.exists(image_path):
            raise ValueError(f"Image file not found: {image_path}")

        try:
            raw_result = None
            errors = []

            try:
                if self.provider == OCRProvider.DEEPSEEK:
                    raw_result = await self._deepseek_ocr(image_path, **kwargs)
                elif self.provider in [
                    OCRProvider.CHANDRA_HF,
                    OCRProvider.CHANDRA_VLLM,
                ]:
                    raw_result = await self._chandra_ocr(image_path, **kwargs)
                elif self.provider == OCRProvider.TESSERACT:
                    raw_result = await self._tesseract_ocr(image_path)
                else:
                    raise ValueError(f"Unknown provider: {self.provider}")

            except Exception as e:
                logger.warning("Primary provider failed: %s", e)
                errors.append(f"{self.provider}: {e}")

                if self.enable_fallback:
                    raw_result = await self._try_fallback_providers(
                        image_path, **kwargs
                    )

                if raw_result is None:
                    raise RuntimeError(f"All OCR providers failed: {errors}")

            result = OCRResult(
                text=raw_result.get("text", ""),
                confidence=raw_result.get("confidence", 0.0),
                document_type=document_type,
                metadata={
                    "provider": self.provider.value,
                    "image_path": image_path,
                    **raw_result.get("metadata", {}),
                },
            )

            if self.enable_ai_parsing and result.text:
                result.structured_data = await self._parse_structure_with_ai(
                    result.text, document_type
                )

            return result

        except Exception as e:
            logger.error(f"OCR processing error: {e}", exc_info=True)
            raise

    async def _deepseek_ocr(self, image_path: str, **kwargs) -> Dict[str, Any]:
        if not self.deepseek_available:
            raise RuntimeError("DeepSeek-OCR not available")

        def _run_inference():
            import torch
            from PIL import Image

            image = Image.open(image_path).convert("RGB")
            inputs = self.deepseek_tokenizer(images=image, return_tensors="pt").to(
                self.deepseek_device
            )

            with torch.no_grad():
                outputs = self.deepseek_model.generate(
                    **inputs,
                    max_new_tokens=4096,
                    do_sample=False,
                    temperature=1.0,
                    num_beams=1,
                )

            generated_text = self.deepseek_tokenizer.batch_decode(
                outputs, skip_special_tokens=True
            )[0]
            return generated_text

        loop = asyncio.get_event_loop()
        generated_text = await loop.run_in_executor(self._executor, _run_inference)

        return {
            "text": generated_text,
            "confidence": 0.91,
            "metadata": {
                "method": "deepseek",
                "device": self.deepseek_device,
                "model": "deepseek-ai/DeepSeek-OCR",
            },
        }

    async def _try_fallback_providers(
        self, image_path: str, **kwargs
    ) -> Optional[Dict[str, Any]]:
        fallback_attempts = []
        if hasattr(self, "chandra_available") and self.chandra_available:
            fallback_attempts.append(("Chandra", self._chandra_ocr))
        if hasattr(self, "tesseract_available") and self.tesseract_available:
            fallback_attempts.append(("Tesseract", self._tesseract_ocr))

        for name, ocr_method in fallback_attempts:
            try:
                logger.info("Trying fallback: %s", name)
                result = await ocr_method(image_path, **kwargs)
                result["metadata"]["fallback_from"] = self.provider.value
                result["metadata"]["used_provider"] = name.lower()
                return result
            except Exception as e:
                logger.warning("Fallback %s failed: {e}", name)
                continue
        return None

    async def _chandra_ocr(
        self, image_path: str, max_tokens: int = 8192, include_images: bool = False
    ) -> Dict[str, Any]:
        if not self.chandra_available:
            raise RuntimeError("Chandra not available")

        def _sync_process():
            from chandra import process_document

            with tempfile.TemporaryDirectory() as output_dir:
                method = "hf" if self.provider == OCRProvider.CHANDRA_HF else "vllm"
                process_document(
                    input_path=image_path,
                    output_dir=output_dir,
                    method=method,
                    max_output_tokens=max_tokens,
                    include_images=include_images,
                    include_headers_footers=False,
                )
                output_file = Path(output_dir) / f"{Path(image_path).stem}.md"
                if output_file.exists():
                    with open(output_file, "r", encoding="utf-8") as f:
                        return f.read()
                return ""

        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(self._executor, _sync_process)

        return {"text": text, "confidence": 0.85, "metadata": {"method": "chandra"}}

    async def _tesseract_ocr(self, image_path: str) -> Dict[str, Any]:
        if not self.tesseract_available:
            raise RuntimeError("Tesseract not available")

        def _sync_process():
            import pytesseract
            from PIL import Image

            image = Image.open(image_path)
            data = pytesseract.image_to_data(
                image, lang="rus+eng", output_type=pytesseract.Output.DICT
            )
            text_parts = []
            confidences = []
            for i, conf in enumerate(data["conf"]):
                if int(conf) > 0:
                    text = data["text"][i]
                    if text.strip():
                        text_parts.append(text)
                        confidences.append(int(conf))
            return (
                " ".join(text_parts),
                sum(confidences) / len(confidences) if confidences else 0,
            )

        loop = asyncio.get_event_loop()
        full_text, avg_confidence = await loop.run_in_executor(
            self._executor, _sync_process
        )

        return {
            "text": full_text,
            "confidence": avg_confidence / 100,
            "metadata": {"method": "tesseract"},
        }

    async def _parse_structure_with_ai(
        self, text: str, document_type: DocumentType
    ) -> Dict[str, Any]:
        try:
            from src.ai.orchestrator import get_orchestrator

            prompt = f"Parse this {document_type.value} document:\n{text}\nReturn JSON."
            result = await get_orchestrator().process_query(
                prompt,
                context={
                    "type": "document_parsing",
                    "document_type": document_type.value,
                },
            )

            # Simple JSON extraction logic (simplified for brevity)
            import json
            import re

            response_text = result.get("answer", "")
            json_match = re.search(r"\{[^}]+\}", response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return {"raw_response": response_text}

        except Exception as e:
            logger.error("AI parsing error: %s", e)
            return {}

    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats"""
        return [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".pdf"]

    async def is_supported_format(self, filename: str) -> bool:
        """Check if file format is supported"""
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.get_supported_formats()

    def estimate_processing_time(self, image_path: str) -> float:
        """Estimate processing time in seconds"""
        try:
            file_size = os.path.getsize(image_path)
            # Rough estimate: 1 sec per 100KB
            return max(1.0, file_size / (100 * 1024))
        except OSError:
            return 5.0

    async def process_from_bytes(
        self,
        file_content: bytes,
        filename: str = "image.png",
        document_type: DocumentType = DocumentType.AUTO,
        **kwargs,
    ) -> OCRResult:
        """Process image from bytes"""
        import tempfile

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(filename)[1]
        ) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        try:
            return await self.process_image(tmp_path, document_type, **kwargs)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def __del__(self):
        self._executor.shutdown(wait=False)


# Singleton instance
_ocr_service: Optional[OCRService] = None


def get_ocr_service(
    provider: Optional[OCRProvider] = None,
    enable_ai_parsing: bool = True,
    enable_fallback: bool = True,
) -> OCRService:
    global _ocr_service
    if _ocr_service is None or provider is not None:
        if provider is None:
            provider_str = settings.ocr_provider
            provider = OCRProvider(provider_str)
        _ocr_service = OCRService(provider, enable_ai_parsing, enable_fallback)
    return _ocr_service


# Utility functions
async def quick_ocr(image_path: str) -> str:
    """
    Быстрое OCR - только текст без парсинга

    Args:
        image_path: Путь к изображению

    Returns:
        Распознанный текст
    """
    service = get_ocr_service(enable_ai_parsing=False)
    result = await service.process_image(image_path)
    return result.text


async def ocr_with_structure(
    image_path: str, document_type: DocumentType = DocumentType.AUTO
) -> Dict[str, Any]:
    """
    OCR с извлечением структуры

    Args:
        image_path: Путь к изображению
        document_type: Тип документа

    Returns:
        Dict с текстом и структурированными данными
    """
    service = get_ocr_service(enable_ai_parsing=True)
    result = await service.process_image(image_path, document_type=document_type)
    return result.to_dict()
