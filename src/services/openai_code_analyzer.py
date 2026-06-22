"""
OpenAI Code Analyzer Service
Специализированный сервис для анализа кода через OpenAI API
Версия: 1.0.0
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

from src.config import settings

_OPENAI_ANALYZER: Optional["OpenAICodeAnalyzer"] = None


def get_openai_analyzer() -> "OpenAICodeAnalyzer":
    """
    Lazy singleton accessor to reuse analyzer in HTTP handlers and tests.
    """
    global _OPENAI_ANALYZER
    if _OPENAI_ANALYZER is None:
        _OPENAI_ANALYZER = OpenAICodeAnalyzer()
    return _OPENAI_ANALYZER


def set_openai_analyzer(analyzer: Optional["OpenAICodeAnalyzer"]) -> None:
    """
    Allow tests to inject a local analyzer implementation.
    """
    global _OPENAI_ANALYZER
    _OPENAI_ANALYZER = analyzer


class OpenAICodeAnalyzer:
    """Сервис для AI анализа кода через OpenAI"""

    def __init__(self):
        self.api_key = settings.openai_api_key

        self.base_url = "https://api.openai.com/v1"
        self.model = "gpt-4-turbo-preview"
        self.timeout = 30.0
        self.enabled = bool(self.api_key and self.api_key != "test")

        if not self.enabled:
            logger.warning("OpenAI API ключ не настроен, AI анализ недоступен")

    async def analyze_code(
        self, code: str, language: str = "bsl", context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Анализ кода через OpenAI с input validation

        Args:
            code: Исходный код для анализа
            language: Язык программирования
            context: Дополнительный контекст

        Returns:
            Список предложений по улучшению кода
        """
        # Input validation
        if not isinstance(code, str) or not code.strip():
            logger.warning(
                "Invalid code in analyze_code",
                extra={"code_type": type(code).__name__ if code else None},
            )
            return []

        # Limit code length (prevent DoS)
        max_code_length = 100000  # 100KB max
        if len(code) > max_code_length:
            logger.warning(
                "Code too long in analyze_code",
                extra={"code_length": len(code), "max_length": max_code_length},
            )
            code = code[:max_code_length]

        if not isinstance(language, str) or not language.strip():
            logger.warning(
                "Invalid language in analyze_code",
                extra={"language_type": type(language).__name__ if language else None},
            )
            language = "bsl"

        if not self.enabled:
            logger.debug(
                "OpenAI недоступен, пропускаем AI анализ", extra={"language": language}
            )
            return []

        try:
            prompt = self._build_analysis_prompt(code, language, context)
            response = await self._make_request(prompt)
            suggestions = self._parse_response(response, code)

            logger.info(
                "AI анализ завершен",
                extra={
                    "suggestions_count": len(suggestions),
                    "language": language,
                    "code_length": len(code),
                },
            )
            return suggestions

        except Exception as e:
            logger.error(
                "Ошибка AI анализа",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "language": language,
                    "code_length": len(code),
                },
                exc_info=True,
            )
            return []  # Возвращаем пустой список при ошибке

    def _build_analysis_prompt(
        self, code: str, language: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Построение промпта для анализа кода 1С"""

        system_prompt = self._get_system_prompt_1c(language)

        user_prompt = f"""Проанализируй следующий код на языке {language} для платформы 1С:Предприятие:

```{language}
{code}
```

Контекст:
{json.dumps(context, indent=2, ensure_ascii=False) if context else 'Не указан'}

Найди проблемы и предложи улучшения в следующих категориях:

1. **Производительность:**
   - Циклы с запросами к БД
   - Неоптимальные алгоритмы
   - Избыточные вычисления
   - Проблемы с кэшированием

2. **Безопасность:**
   - SQL инъекции
   - Хардкод паролей/секретов
   - Отсутствие валидации входных данных
   - Небезопасное использование API

3. **Best Practices:**
   - Использование устаревших методов
   - Отсутствие обработки исключений
   - Нарушение соглашений именования
   - Плохая структура кода

4. **Потенциальные баги:**
   - Обработка null/undefined
   - Ошибки логики
   - Проблемы с типами данных
   - Граничные случаи

Верни результат в формате JSON массива:
[
  {{
    "type": "error|warning|info|hint",
    "severity": "critical|high|medium|low",
    "message": "Краткое описание проблемы (максимум 100 символов)",
    "description": "Подробное описание проблемы и почему это проблема",
    "suggestion": "Конкретное предложение по исправлению",
    "code": "Пример исправленного кода (если применимо)",
    "line": <номер строки>,
    "column": <номер колонки (опционально)>,
    "category": "performance|security|best-practice|style|bug|optimization",
    "autoFixable": true|false,
    "confidence": <0.0-1.0>,
    "reasons": ["Причина 1", "Причина 2"]
  }}
]

Важно:
- Будь конкретным и практичным
- Предлагай реальные решения, а не абстрактные рекомендации
- Учитывай специфику платформы 1С:Предприятие
- Приоритизируй критичные проблемы
- Если проблем нет, верни пустой массив []"""

        return {"system_prompt": system_prompt, "user_prompt": user_prompt}

    def _get_system_prompt_1c(self, language: str) -> str:
        """Системный промпт для анализа кода 1С"""

        if language == "bsl":
            return """Ты - опытный code reviewer для языка 1С (BSL) с более чем 15-летним опытом работы с платформой 1С:Предприятие.

Твоя специализация:
- Глубокая экспертиза в языке BSL и платформе 1С
- Знание всех типовых конфигураций (Бухгалтерия, УТ, ERP и др.)
- Понимание специфики российской разработки и бизнес-процессов
- Опыт оптимизации производительности больших баз данных
- Знание всех версий платформы от 8.2 до 8.3.24+

Основные принципы анализа:
1. **Производительность критична** - база может содержать миллионы записей
2. **Безопасность важна** - код работает с финансовыми данными
3. **Поддерживаемость** - код должен быть понятен через год
4. **Стандарты 1С** - следование принятым практикам платформы

Особенности платформы 1С:
- Запросы к БД дорогие, особенно в циклах
- Используй ПроверитьТип() вместо Тип()
- Всегда обрабатывай исключения блоком Попытка-Исключение
- Кэшируй метаданные объектов
- Используй параметры запросов вместо конкатенации строк
- Избегай N+1 проблем в запросах
- Оптимизируй использование массивов и структур

Будь строгим но справедливым. Критикуй код, но предлагай конструктивные решения."""

        else:
            return f"""Ты - опытный code reviewer для языка {language} с глубоким пониманием best practices.

Анализируй код и предлагай улучшения в категориях:
- Производительность
- Безопасность
- Best practices
- Потенциальные баги

Будь конкретным и практичным в рекомендациях."""

    async def _make_request(self, prompt: Dict[str, str], max_retries: int = 3) -> str:
        """
        Отправка запроса к OpenAI API с retry logic

        Best practices:
        - Exponential backoff для retry
        - Retry только для transient errors (5xx, timeout, connection errors)
        - Timeout для всех запросов
        """
        import asyncio

        last_exception = None

        for attempt in range(max_retries):
            try:
                timeout = httpx.Timeout(self.timeout, connect=10.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    }

                    payload = {
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": prompt["system_prompt"]},
                            {"role": "user", "content": prompt["user_prompt"]},
                        ],
                        "temperature": 0.3,  # Низкая температура для более детерминированных ответов
                        "max_tokens": 3000,  # Достаточно для детального анализа
                        "response_format": {
                            "type": "json_object"
                        },  # Требуем JSON формат
                    }

                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )

                    response.raise_for_status()
                    data = response.json()

                    return data["choices"][0]["message"]["content"]

            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        "Timeout при запросе к OpenAI, повтор",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "wait_time": wait_time,
                        },
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "Все попытки запроса к OpenAI завершились timeout",
                        extra={"max_retries": max_retries, "timeout": self.timeout},
                        exc_info=True,
                    )
                    raise

            except httpx.HTTPStatusError as e:
                # Retry только для 5xx ошибок (server errors)
                if e.response.status_code >= 500 and attempt < max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        "Server error при запросе к OpenAI, повтор",
                        extra={
                            "status_code": e.response.status_code,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "wait_time": wait_time,
                        },
                    )
                    await asyncio.sleep(wait_time)
                    last_exception = e
                else:
                    # 4xx ошибки (client errors) не ретраим
                    logger.error(
                        "HTTP error при запросе к OpenAI",
                        extra={
                            "status_code": e.response.status_code,
                            "response_text": (
                                e.response.text[:500] if e.response.text else None
                            ),
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                        },
                        exc_info=True,
                    )
                    raise

            except httpx.ConnectError as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        "Connection error при запросе к OpenAI, повтор",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "wait_time": wait_time,
                            "error": str(e),
                        },
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "Все попытки подключения к OpenAI завершились ошибкой",
                        extra={
                            "max_retries": max_retries,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                        exc_info=True,
                    )
                    raise

            except Exception as e:
                # Неожиданные ошибки не ретраим
                logger.error(
                    "Неожиданная ошибка при запросе к OpenAI",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                    },
                    exc_info=True,
                )
                raise

        # Если дошли сюда, все попытки исчерпаны
        if last_exception:
            raise last_exception
        raise Exception("Все попытки запроса исчерпаны")

    def _parse_response(self, response: str, code: str) -> List[Dict[str, Any]]:
        """Парсинг ответа OpenAI"""

        suggestions = []

        try:
            # Извлечение JSON из ответа
            response = response.strip()

            # Если ответ начинается с markdown code block, извлекаем JSON
            if response.startswith("```json"):
                response = response[7:]  # Убираем ```json
            elif response.startswith("```"):
                response = response[3:]  # Убираем ```

            if response.endswith("```"):
                response = response[:-3]  # Убираем закрывающий ```

            response = response.strip()

            # Парсинг JSON
            if response.startswith("{"):
                # Если ответ - объект с массивом suggestions
                data = json.loads(response)
                if "suggestions" in data:
                    suggestions_raw = data["suggestions"]
                elif isinstance(data, list):
                    suggestions_raw = data
                else:
                    suggestions_raw = [data]
            elif response.startswith("["):
                # Если ответ - массив
                suggestions_raw = json.loads(response)
            else:
                logger.warning(
                    "Неожиданный формат ответа OpenAI",
                    extra={"response_preview": response[:100]},
                )
                return []

            # Нормализация предложений
            for i, suggestion in enumerate(suggestions_raw):
                normalized = self._normalize_suggestion(suggestion, code, i)
                if normalized:
                    suggestions.append(normalized)

            logger.debug(
                "Распарсено предложений из ответа OpenAI",
                extra={
                    "suggestions_count": len(suggestions),
                    "suggestions_raw_count": len(suggestions_raw),
                },
            )

        except json.JSONDecodeError as e:
            logger.error(
                "Ошибка парсинга JSON ответа",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "response_preview": response[:500] if response else None,
                },
                exc_info=True,
            )
            return []
        except Exception as e:
            logger.error(
                "Ошибка парсинга ответа",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return []

        return suggestions

    def _normalize_suggestion(
        self, suggestion: Dict[str, Any], code: str, index: int
    ) -> Optional[Dict[str, Any]]:
        """Нормализация предложения из AI"""

        try:
            # Валидация обязательных полей
            if "message" not in suggestion and "description" not in suggestion:
                return None

            # Нормализация полей
            normalized = {
                "id": f"ai-{int(datetime.now().timestamp() * 1000)}-{index}",
                "type": suggestion.get("type", "info"),
                "severity": suggestion.get("severity", "medium"),
                "message": suggestion.get(
                    "message", suggestion.get("description", "")[:100]
                ),
                "description": suggestion.get(
                    "description", suggestion.get("message", "")
                ),
                "suggestion": suggestion.get("suggestion"),
                "code": suggestion.get("code"),
                "position": {
                    "line": suggestion.get("line", 1),
                    "column": suggestion.get("column", 1),
                    "endLine": suggestion.get("endLine"),
                    "endColumn": suggestion.get("endColumn"),
                },
                "category": suggestion.get("category", "best-practice"),
                "autoFixable": suggestion.get("autoFixable", False),
                "confidence": min(
                    1.0, max(0.0, float(suggestion.get("confidence", 0.7)))
                ),
            }

            # Валидация значений
            if normalized["type"] not in ["error", "warning", "info", "hint"]:
                normalized["type"] = "info"

            if normalized["severity"] not in ["critical", "high", "medium", "low"]:
                normalized["severity"] = "medium"

            if normalized["category"] not in [
                "performance",
                "security",
                "best-practice",
                "style",
                "bug",
                "optimization",
            ]:
                normalized["category"] = "best-practice"

            # Проверка что номер строки в пределах кода
            lines_count = len(code.split("\n"))
            if normalized["position"]["line"] > lines_count:
                normalized["position"]["line"] = 1

            return normalized

        except Exception as e:
            logger.error(
                "Ошибка нормализации предложения",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "suggestion_index": index,
                },
                exc_info=True,
            )
            return None

    async def generate_test_cases(
        self, code: str, function_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Генерация тест-кейсов через OpenAI

        Args:
            code: Код функции для тестирования
            function_name: Имя функции (опционально)

        Returns:
            Список тест-кейсов
        """
        if not self.enabled:
            return []

        try:
            prompt = self._build_test_generation_prompt(code, function_name)
            response = await self._make_request(prompt)
            test_cases = self._parse_test_cases_response(response)

            logger.info(
                "AI сгенерировано тест-кейсов",
                extra={
                    "test_cases_count": len(test_cases),
                    "function_name": function_name,
                },
            )
            return test_cases

        except Exception as e:
            logger.error(
                "Ошибка генерации тест-кейсов",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "function_name": function_name,
                },
                exc_info=True,
            )
            return []

    def _build_test_generation_prompt(
        self, code: str, function_name: Optional[str] = None
    ) -> Dict[str, str]:
        """Построение промпта для генерации тест-кейсов"""

        system_prompt = """Ты - эксперт по тестированию кода на языке 1С (BSL).

Твоя задача - создать качественные тест-кейсы включая:
1. Положительные случаи (happy path)
2. Отрицательные случаи (validation errors)
3. Граничные случаи (boundary values)
4. Крайние случаи (edge cases)

Верни результат в формате JSON массива тест-кейсов."""

        user_prompt = f"""Создай тест-кейсы для следующей функции{' ' + function_name if function_name else ''}:

```bsl
{code}
```

Верни JSON массив:
[
  {{
    "name": "название_теста",
    "description": "описание что тестируется",
    "input": {{"param1": "value1", "param2": "value2"}},
    "expectedOutput": "ожидаемый результат",
    "type": "positive|negative|edge|boundary",
    "category": "unit|integration|e2e"
  }}
]"""

        return {"system_prompt": system_prompt, "user_prompt": user_prompt}

    def _parse_test_cases_response(self, response: str) -> List[Dict[str, Any]]:
        """Парсинг ответа с тест-кейсами"""

        try:
            # Очистка markdown обертки
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            response = response.strip()

            # Парсинг JSON
            if response.startswith("["):
                test_cases = json.loads(response)
            elif response.startswith("{"):
                data = json.loads(response)
                test_cases = data.get("testCases", data.get("tests", []))
            else:
                return []

            # Нормализация
            normalized = []
            for i, case in enumerate(test_cases):
                normalized_case = {
                    "id": f"ai-test-{int(datetime.now().timestamp() * 1000)}-{i}",
                    "name": case.get("name", f"Test{i+1}"),
                    "description": case.get("description", ""),
                    "input": case.get("input", {}),
                    "expectedOutput": case.get("expectedOutput"),
                    "type": case.get("type", "unit"),
                    "category": case.get("category", case.get("type", "positive")),
                }
                normalized.append(normalized_case)

            return normalized

        except Exception as e:
            logger.error(
                "Ошибка парсинга тест-кейсов",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return []
