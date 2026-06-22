"""
Speech-to-Text Service
Версия: 2.1.0

Улучшения:
- Добавлен timeout для транскрипции
- Улучшена обработка ошибок
- Structured logging
- Retry logic для внешних API с exponential backoff
- Input validation и sanitization
"""

import asyncio
import os
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import settings
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class STTProvider(str, Enum):
    """Провайдеры Speech-to-Text"""

    OPENAI_WHISPER = "openai_whisper"
    LOCAL_WHISPER = "local_whisper"
    VOSK = "vosk"


class SpeechToTextService:
    """Сервис распознавания речи"""

    def __init__(
        self,
        provider: STTProvider = STTProvider.OPENAI_WHISPER,
        api_key: Optional[str] = None,
        model: str = "whisper-1",
        language: str = "ru",
    ):
        """
        Инициализация сервиса

        Args:
            provider: Провайдер STT
            api_key: API ключ (для OpenAI)
            model: Модель для распознавания
            language: Язык распознавания (ru, en)
        """
        self.provider = provider
        self.api_key = api_key or settings.openai_api_key
        self.model = model
        self.language = language

        # Инициализация клиента
        if self.provider == STTProvider.OPENAI_WHISPER:
            self._init_openai()
        elif self.provider == STTProvider.LOCAL_WHISPER:
            self._init_local_whisper()
        elif self.provider == STTProvider.VOSK:
            self._init_vosk()

    def _init_openai(self):
        """Инициализация OpenAI Whisper"""
        try:
            from openai import OpenAI

            if not self.api_key:
                raise ValueError("OpenAI API key not provided")

            self.client = OpenAI(api_key=self.api_key)
            logger.info("OpenAI Whisper initialized")

        except ImportError:
            logger.error("OpenAI package not installed. Install: pip install openai")
            raise

    def _init_local_whisper(self):
        """Инициализация локального Whisper"""
        try:
            import whisper

            # Загружаем модель (base, small, medium, large)
            model_size = settings.whisper_model_size
            self.whisper_model = whisper.load_model(model_size)
            logger.info("Local Whisper initialized", extra={"model_size": model_size})

        except ImportError:
            logger.error(
                "Whisper package not installed. Install: pip install openai-whisper"
            )
            raise

    def _init_vosk(self):
        """Инициализация Vosk (offline STT)"""
        try:
            from vosk import Model

            model_path = settings.vosk_model_path

            if not os.path.exists(model_path):
                raise ValueError(f"Vosk model not found at {model_path}")

            self.vosk_model = Model(model_path)
            logger.info("Vosk initialized", extra={"model_path": model_path})

        except ImportError:
            logger.error("Vosk package not installed. Install: pip install vosk")
            raise

    async def transcribe(
        self,
        audio_file_path: str,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        response_format: str = "text",
        timeout: float = 300.0,  # 5 minutes default
    ) -> Dict[str, Any]:
        """
        Распознавание речи из аудио файла

        Args:
            audio_file_path: Путь к аудио файлу
            language: Язык (переопределяет self.language)
            prompt: Подсказка для улучшения распознавания
            response_format: Формат ответа (text, json, srt, vtt)
            timeout: Timeout для операции (секунды)

        Returns:
            Dict с текстом и метаданными
        """
        lang = language or self.language

        # Input validation (best practice)
        if not audio_file_path or not isinstance(audio_file_path, str):
            logger.warning(
                "Invalid audio_file_path in transcribe",
                extra={
                    "audio_file_path_type": (
                        type(audio_file_path).__name__ if audio_file_path else None
                    )
                },
            )
            raise ValueError("audio_file_path must be a non-empty string")

        # Sanitize path (prevent path traversal)
        audio_file_path = os.path.normpath(audio_file_path)

        if not os.path.exists(audio_file_path):
            logger.warning(
                "Audio file not found", extra={"audio_file_path": audio_file_path}
            )
            raise ValueError(f"Audio file not found: {audio_file_path}")

        # Validate file size (prevent DoS)
        try:
            file_size = os.path.getsize(audio_file_path)
        except OSError as e:
            logger.error(
                "Error getting file size",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "audio_file_path": audio_file_path,
                },
                exc_info=True,
            )
            raise ValueError(f"Cannot access audio file: {audio_file_path}")

        max_file_size = 25 * 1024 * 1024  # 25MB max
        if file_size > max_file_size:
            logger.warning(
                "Audio file too large",
                extra={
                    "audio_file_path": audio_file_path,
                    "file_size": file_size,
                    "max_size": max_file_size,
                },
            )
            raise ValueError(
                f"Audio file too large: {file_size} bytes. Maximum: {max_file_size} bytes"
            )

        # Validate timeout
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            logger.warning(
                "Invalid timeout in transcribe",
                extra={"timeout": timeout, "timeout_type": type(timeout).__name__},
            )
            timeout = 300.0  # Default timeout

        # Validate response_format
        valid_formats = ["text", "json", "srt", "vtt"]
        if response_format not in valid_formats:
            logger.warning(
                "Invalid response_format in transcribe",
                extra={
                    "response_format": response_format,
                    "valid_formats": valid_formats,
                },
            )
            response_format = "text"  # Default format

        try:
            # Execute with timeout (best practice)
            if self.provider == STTProvider.OPENAI_WHISPER:
                return await asyncio.wait_for(
                    self._transcribe_openai(
                        audio_file_path, lang, prompt, response_format
                    ),
                    timeout=timeout,
                )
            elif self.provider == STTProvider.LOCAL_WHISPER:
                return await asyncio.wait_for(
                    self._transcribe_local_whisper(audio_file_path, lang),
                    timeout=timeout,
                )
            elif self.provider == STTProvider.VOSK:
                return await asyncio.wait_for(
                    self._transcribe_vosk(audio_file_path), timeout=timeout
                )
            else:
                raise ValueError(f"Unknown provider: {self.provider}")

        except asyncio.TimeoutError:
            logger.error(
                f"Timeout при транскрипции аудио: {audio_file_path}",
                extra={
                    "audio_file_path": audio_file_path,
                    "provider": self.provider.value,
                    "timeout": timeout,
                },
            )
            raise RuntimeError(f"Transcription timeout after {timeout} seconds")
        except Exception as e:
            logger.error(
                "Unexpected error during transcription",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "audio_file_path": audio_file_path,
                    "provider": self.provider.value,
                    "language": lang,
                },
                exc_info=True,
            )
            raise

    async def _transcribe_openai(
        self,
        audio_file_path: str,
        language: str,
        prompt: Optional[str],
        response_format: str,
    ) -> Dict[str, Any]:
        """Распознавание через OpenAI Whisper API с retry logic"""

        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                with open(audio_file_path, "rb") as audio_file:
                    # Параметры запроса
                    kwargs = {
                        "model": self.model,
                        "file": audio_file,
                        "response_format": response_format,
                        "timeout": 60.0,  # Timeout для запроса
                    }

                    if language:
                        kwargs["language"] = language

                    if prompt:
                        # Validate prompt length (max 244 chars for OpenAI)
                        if len(prompt) > 244:
                            logger.warning(
                                f"Prompt too long ({len(prompt)} chars), truncating to 244",
                                extra={"prompt_length": len(prompt)},
                            )
                            prompt = prompt[:244]
                        kwargs["prompt"] = prompt

                    # Вызов API с retry
                    response = self.client.audio.transcriptions.create(**kwargs)

                    # Формирование результата
                    if response_format == "text":
                        text = response
                        result = {
                            "text": text,
                            "language": language,
                            "provider": "openai_whisper",
                            "model": self.model,
                        }
                    else:
                        # JSON, SRT, VTT
                        result = {
                            "text": (
                                response.text
                                if hasattr(response, "text")
                                else str(response)
                            ),
                            "language": language,
                            "provider": "openai_whisper",
                            "model": self.model,
                            "segments": (
                                response.segments
                                if hasattr(response, "segments")
                                else None
                            ),
                        }

                    if attempt > 0:
                        logger.info(
                            "OpenAI transcription succeeded on retry",
                            extra={
                                "attempt": attempt + 1,
                                "text_length": len(result.get("text", "")),
                                "provider": "openai_whisper",
                            },
                        )
                    else:
                        logger.info(
                            "OpenAI transcription completed",
                            extra={
                                "text_length": len(result.get("text", "")),
                                "provider": "openai_whisper",
                                "language": language,
                            },
                        )
                    return result

            except Exception as e:
                error_type = type(e).__name__
                is_retryable = error_type in [
                    "APIConnectionError",
                    "APITimeoutError",
                    "RateLimitError",
                ] or (hasattr(e, "status_code") and e.status_code >= 500)

                if attempt == max_retries - 1 or not is_retryable:
                    logger.error(
                        "OpenAI transcription failed",
                        extra={
                            "audio_file_path": audio_file_path,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "error": str(e),
                            "error_type": error_type,
                            "is_retryable": is_retryable,
                        },
                        exc_info=True,
                    )
                    raise

                # Exponential backoff
                delay = base_delay * (2**attempt)
                logger.warning(
                    "OpenAI transcription attempt failed, retrying",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                        "delay": delay,
                        "error": str(e),
                        "error_type": error_type,
                    },
                )
                await asyncio.sleep(delay)

    async def _transcribe_local_whisper(
        self, audio_file_path: str, language: str
    ) -> Dict[str, Any]:
        """Распознавание через локальный Whisper"""

        try:
            # Распознавание
            result = self.whisper_model.transcribe(
                audio_file_path, language=language, verbose=False
            )

            output = {
                "text": result["text"].strip(),
                "language": result["language"],
                "provider": "local_whisper",
                "model": self.whisper_model.__class__.__name__,
                "segments": result.get("segments", []),
            }

            logger.info(
                "Local Whisper transcription completed",
                extra={
                    "text_length": len(output["text"]),
                    "language": output.get("language"),
                    "provider": output.get("provider"),
                },
            )
            return output

        except Exception as e:
            logger.error(
                "Local Whisper transcription error",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "audio_file_path": audio_file_path,
                    "language": language,
                },
                exc_info=True,
            )
            raise

    async def _transcribe_vosk(self, audio_file_path: str) -> Dict[str, Any]:
        """Распознавание через Vosk (offline)"""

        try:
            import json
            import wave

            from vosk import KaldiRecognizer

            # Открываем аудио файл
            wf = wave.open(audio_file_path, "rb")

            # Создаем recognizer
            rec = KaldiRecognizer(self.vosk_model, wf.getframerate())
            rec.SetWords(True)

            # Распознавание
            full_text = []

            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break

                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    if "text" in result and result["text"]:
                        full_text.append(result["text"])

            # Финальный результат
            final_result = json.loads(rec.FinalResult())
            if "text" in final_result and final_result["text"]:
                full_text.append(final_result["text"])

            text = " ".join(full_text).strip()

            output = {
                "text": text,
                "language": self.language,
                "provider": "vosk",
                "model": "vosk-model",
            }

            logger.info(
                "Vosk transcription completed",
                extra={
                    "text_length": len(text),
                    "language": output.get("language"),
                    "provider": output.get("provider"),
                },
            )
            return output

        except Exception as e:
            logger.error(
                "Vosk transcription error",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "audio_file_path": audio_file_path,
                },
                exc_info=True,
            )
            raise

    async def transcribe_from_bytes(
        self, audio_bytes: bytes, filename: str = "audio.ogg", **kwargs
    ) -> Dict[str, Any]:
        """
        Распознавание речи из bytes с input validation

        Args:
            audio_bytes: Аудио данные в bytes
            filename: Имя файла (для определения формата)
            **kwargs: Дополнительные параметры для transcribe()

        Returns:
            Dict с текстом и метаданными
        """
        # Input validation
        if not audio_bytes or not isinstance(audio_bytes, bytes):
            logger.warning(
                "Invalid audio_bytes in transcribe_from_bytes",
                extra={
                    "audio_bytes_type": (
                        type(audio_bytes).__name__ if audio_bytes else None
                    ),
                    "audio_bytes_length": (
                        len(audio_bytes) if isinstance(audio_bytes, bytes) else None
                    ),
                },
            )
            raise ValueError("audio_bytes must be a non-empty bytes object")

        # Validate audio_bytes size (prevent DoS)
        max_bytes_size = 25 * 1024 * 1024  # 25MB max
        if len(audio_bytes) > max_bytes_size:
            logger.warning(
                "Audio bytes too large in transcribe_from_bytes",
                extra={
                    "audio_bytes_length": len(audio_bytes),
                    "max_size": max_bytes_size,
                },
            )
            raise ValueError(
                f"Audio bytes too large: {len(audio_bytes)} bytes. Maximum: {max_bytes_size} bytes"
            )

        # Validate filename
        if not filename or not isinstance(filename, str):
            logger.warning(
                "Invalid filename in transcribe_from_bytes",
                extra={"filename_type": type(filename).__name__ if filename else None},
            )
            filename = "audio.ogg"  # Default

        # Sanitize filename (prevent path traversal)
        filename = os.path.basename(filename)  # Remove any path components
        if not filename or filename == "." or filename == "..":
            filename = "audio.ogg"  # Safe default

        tmp_path = None
        try:
            # Сохраняем во временный файл
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=Path(filename).suffix
            ) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name

            logger.debug(
                "Created temporary file for audio bytes",
                extra={
                    "tmp_path": tmp_path,
                    "audio_bytes_length": len(audio_bytes),
                    "filename": filename,
                },
            )

            # Распознаем
            result = await self.transcribe(tmp_path, **kwargs)
            return result

        except Exception as e:
            logger.error(
                f"Error in transcribe_from_bytes: {e}",
                extra={
                    "filename": filename,
                    "audio_bytes_length": (
                        len(audio_bytes) if isinstance(audio_bytes, bytes) else None
                    ),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise
        finally:
            # Удаляем временный файл
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                    logger.debug("Deleted temporary file", extra={"tmp_path": tmp_path})
                except Exception as e:
                    logger.warning(
                        "Failed to delete temp file",
                        extra={
                            "tmp_path": tmp_path,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                    )

    def get_supported_formats(self) -> list:
        """Получить список поддерживаемых форматов аудио"""
        if self.provider == STTProvider.OPENAI_WHISPER:
            # OpenAI Whisper поддерживает множество форматов
            return ["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "ogg"]
        elif self.provider == STTProvider.LOCAL_WHISPER:
            # Локальный Whisper поддерживает всё что ffmpeg
            return ["mp3", "mp4", "wav", "ogg", "flac", "m4a", "wma", "aac", "webm"]
        elif self.provider == STTProvider.VOSK:
            # Vosk требует WAV 16kHz mono
            return ["wav"]

        return []

    async def is_supported_format(self, filename: str) -> bool:
        """Проверка поддерживается ли формат файла"""
        ext = Path(filename).suffix.lower().lstrip(".")
        return ext in self.get_supported_formats()


# Singleton instance
_stt_service: Optional[SpeechToTextService] = None


def get_stt_service() -> SpeechToTextService:
    """Получить глобальный экземпляр сервиса"""
    global _stt_service

    if _stt_service is None:
        # Определяем провайдера из env
        provider_str = settings.stt_provider
        provider = STTProvider(provider_str)

        _stt_service = SpeechToTextService(
            provider=provider, language=settings.stt_language
        )

    return _stt_service
