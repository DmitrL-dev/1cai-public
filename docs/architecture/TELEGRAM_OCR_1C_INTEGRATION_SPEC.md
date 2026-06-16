# Telegram Bot + OCR + 1C Integration Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - такая комбинация уникальна

---

## Обзор

**Telegram Bot + OCR + 1C Integration Standard** — формальная спецификация для уникальной интеграции Telegram Bot с OCR и 1C. Определяет голосовые запросы к AI через Telegram, OCR документов через Telegram и автоматический ввод данных в 1C.

---

## 1. Голосовые запросы к AI через Telegram

### 1.1 Обработка голосовых сообщений

```python
async def process_voice_message(
    voice_file: bytes,
    user_id: str,
) -> Dict[str, Any]:
    """
    Обработка голосового сообщения через Telegram.
    
    Returns:
        {
            "text": str,                 # Распознанный текст
            "query_result": Dict,        # Результат AI запроса
            "language": str,             # Определенный язык
        }
    """
    # 1. Распознавание речи через Whisper
    from src.services.ocr_service import OCRService
    
    ocr_service = OCRService()
    text = await ocr_service.speech_to_text(voice_file)
    
    # 2. Обработка запроса через AI Orchestrator
    from src.ai.orchestrator import AIOrchestrator
    
    orchestrator = AIOrchestrator()
    result = await orchestrator.process_query(
        text,
        context={"user_id": user_id, "source": "telegram_voice"},
    )
    
    return {
        "text": text,
        "query_result": result,
        "language": detect_language(text),
    }
```

---

## 2. OCR документов через Telegram

### 2.1 Обработка документов

```python
async def process_document_ocr(
    document_file: bytes,
    document_type: str,
    user_id: str,
) -> Dict[str, Any]:
    """
    OCR обработка документа через Telegram.
    
    Returns:
        {
            "extracted_data": Dict,      # Извлеченные данные
            "structured_data": Dict,     # Структурированные данные
            "1c_document": Dict,         # Документ для создания в 1C
        }
    """
    # 1. OCR обработка через DeepSeek-OCR
    from src.services.ocr_service import OCRService
    
    ocr_service = OCRService()
    ocr_result = await ocr_service.process_document(document_file, document_type)
    
    # 2. AI парсинг структуры документа
    parsed_structure = await ai_parse_document_structure(ocr_result["text"])
    
    # 3. Валидация извлеченных данных
    validated_data = validate_extracted_data(parsed_structure, document_type)
    
    # 4. Формирование документа 1C
    document_1c = format_for_1c(validated_data, document_type)
    
    return {
        "extracted_data": ocr_result["text"],
        "structured_data": parsed_structure,
        "1c_document": document_1c,
    }
```

---

## 3. Автоматический ввод данных в 1C

### 3.1 Создание документа в 1C

```python
async def create_1c_document_from_ocr(
    structured_data: Dict[str, Any],
    document_type: str,
) -> Dict[str, Any]:
    """
    Создание документа в 1C из OCR данных.
    
    Returns:
        {
            "document_id": str,
            "status": str,
            "validation_errors": List[str],
        }
    """
    # Определение типа документа 1C
    metadata_path = map_document_type_to_1c(document_type)
    
    # Валидация данных
    validation_errors = validate_1c_document_data(structured_data, metadata_path)
    
    if validation_errors:
        return {
            "document_id": None,
            "status": "validation_failed",
            "validation_errors": validation_errors,
        }
    
    # Создание документа через 1C API
    # (интеграция с 1C через HTTP сервисы или COM)
    document_id = await create_1c_document(metadata_path, structured_data)
    
    return {
        "document_id": document_id,
        "status": "created",
        "validation_errors": [],
    }
```

---

## 4. JSON Schema для OCR результатов

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/ocr-result/v1",
  "title": "OCRResult",
  "type": "object",
  "required": ["text", "document_type"],
  "properties": {
    "text": {"type": "string"},
    "document_type": {"type": "string"},
    "structured_data": {"type": "object"},
    "1c_document": {"type": "object"},
    "confidence": {"type": "number"},
    "validation_errors": {
      "type": "array",
      "items": {"type": "string"}
    }
  }
}
```

---

**Примечание:** Этот стандарт обеспечивает уникальную интеграцию Telegram + OCR + 1C для автоматизации документооборота.

