
"""
API для импорта данных в базу знаний из различных источников.

Версия: 1.0.0
"""

import csv
import io
import json
from typing import Any, Dict, List

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.services.configuration_knowledge_base import get_knowledge_base

router = APIRouter(prefix="/api/knowledge-base", tags=["Knowledge Base Import"])

kb = get_knowledge_base()
logger = StructuredLogger(__name__).logger


# Модели данных
class ImportRequest(BaseModel):
    """Модель запроса на импорт данных."""

    config_name: str = Field(..., description="Название конфигурации")
    source: str = Field(default="manual", description="Источник данных")
    overwrite: bool = Field(
        default=False, description="Перезаписать существующие данные")


class ModuleImport(BaseModel):
    """Модель импорта модуля."""

    name: str
    description: str = ""
    code: str = ""
    functions: List[Dict[str, Any]] = []
    object_type: str | None = None
    object_name: str | None = None
    module_type: str | None = None


class BestPracticeImport(BaseModel):
    """Модель импорта лучшей практики."""

    title: str
    description: str
    category: str = "general"
    code_examples: List[str] = []
    tags: List[str] = []


class BulkImportRequest(BaseModel):
    """Модель массового импорта."""

    config_name: str
    modules: List[ModuleImport] = []
    best_practices: List[BestPracticeImport] = []
    source: str = "import"


# Эндпоинты
@router.post("/import/json")
async def import_from_json(config_name: str, file: UploadFile = File(...), overwrite: bool = False) -> Dict[str, Any]:
    """Импортирует данные из JSON файла.

    Args:
        config_name: Название конфигурации.
        file: Загружаемый JSON файл.
        overwrite: Флаг перезаписи существующих данных.

    Returns:
        Dict[str, Any]: Результат импорта.

    Raises:
        HTTPException: Если произошла ошибка при импорте.
    """
    try:
        content = await file.read()
        data = json.loads(content)

        modules_count = 0
        practices_count = 0

        if "modules" in data:
            for module in data["modules"]:
                kb.add_module_documentation(
                    config_name=config_name, module_name=module.get("name", ""), documentation=module
                )
                modules_count += 1

        if "best_practices" in data:
            for practice in data["best_practices"]:
                kb.add_best_practice(
                    config_name=config_name, category=practice.get("category", "general"), practice=practice
                )
                practices_count += 1

        return {"success": True, "modules_imported": modules_count, "best_practices_imported": practices_count}
    except Exception as e:
        logger.error(f"Error importing from JSON: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/csv")
async def import_from_csv(config_name: str, file: UploadFile = File(...), type: str = "modules") -> Dict[str, Any]:
    """Импортирует данные из CSV файла.

    Args:
        config_name: Название конфигурации.
        file: Загружаемый CSV файл.
        type: Тип данных ("modules" или "best_practices").

    Returns:
        Dict[str, Any]: Результат импорта.

    Raises:
        HTTPException: Если произошла ошибка при импорте.
    """
    try:
        content = await file.read()
        decoded = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))

        count = 0
        for row in reader:
            if type == "modules":
                kb.add_module_documentation(
                    config_name=config_name, module_name=row.get("name", ""), documentation=row)
            elif type == "best_practices":
                kb.add_best_practice(config_name=config_name, category=row.get(
                    "category", "general"), practice=row)
            count += 1

        return {"success": True, "imported": count}
    except Exception as e:
        logger.error(f"Error importing from CSV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/bulk")
async def bulk_import(request: BulkImportRequest) -> Dict[str, Any]:
    """Выполняет массовый импорт модулей и лучших практик.

    Args:
        request: Объект запроса с данными для импорта.

    Returns:
        Dict[str, Any]: Результат импорта.

    Raises:
        HTTPException: Если произошла ошибка при импорте.
    """
    try:
        modules_count = 0
        for module in request.modules:
            kb.add_module_documentation(
                config_name=request.config_name, module_name=module.name, documentation=module.model_dump()
            )
            modules_count += 1

        practices_count = 0
        for practice in request.best_practices:
            kb.add_best_practice(
                config_name=request.config_name, category=practice.category, practice=practice.model_dump()
            )
            practices_count += 1

        return {"success": True, "modules_imported": modules_count, "best_practices_imported": practices_count}
    except Exception as e:
        logger.error(f"Error in bulk import: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates/json")
async def download_json_template() -> StreamingResponse:
    """Скачивает шаблон JSON для импорта.

    Returns:
        StreamingResponse: Файл шаблона.
    """
    template = {
        "modules": [
            {"name": "ОбщийМодуль_Пример", "description": "Описание модуля",
                "code": "// Код модуля", "functions": []}
        ],
        "best_practices": [
            {
                "title": "Название практики",
                "description": "Описание",
                "category": "performance",
                "code_examples": [],
                "tags": [],
            }
        ],
    }

    json_str = json.dumps(template, ensure_ascii=False, indent=2)
    return StreamingResponse(
        io.BytesIO(json_str.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=template.json"},
    )


@router.get("/templates/csv")
async def download_csv_template(type: str = "modules") -> StreamingResponse:
    """Скачивает шаблон CSV для импорта.

    Args:
        type: Тип шаблона ("modules" или "best_practices").

    Returns:
        StreamingResponse: Файл шаблона.
    """
    if type == "modules":
        csv_content = "name,description,code,object_type,object_name\n"
        csv_content += "ОбщийМодуль_Пример,Описание,// Код,CommonModule,Пример\n"
    else:
        csv_content = "title,description,category\n"
        csv_content += "Название практики,Описание,performance\n"

    return StreamingResponse(
        io.BytesIO(csv_content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=template_{type}.csv"},
    )
