"""
API endpoints для работы с базой знаний по конфигурациям 1С.

Версия: 1.0.0
"""

from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.services.configuration_knowledge_base import get_knowledge_base

logger = StructuredLogger(__name__).logger
router = APIRouter()


# ==================== МОДЕЛИ ДАННЫХ ====================


class ConfigurationRequest(BaseModel):
    """Модель запроса информации о конфигурации."""

    configName: Literal[
        "erp", "ut", "zup", "buh", "holding", "buhbit", "do", "ka"
    ] = Field(..., description="Название конфигурации")


class ModuleDocumentationRequest(BaseModel):
    """Модель запроса на добавление документации модуля."""

    configName: str
    moduleName: str
    documentation: dict


class BestPracticeRequest(BaseModel):
    """Модель запроса на добавление лучшей практики."""

    configName: str
    category: str
    practice: dict


class PatternSearchRequest(BaseModel):
    """Модель запроса на поиск паттернов."""

    configName: Optional[str] = None
    patternType: Optional[str] = None
    query: Optional[str] = None


class CodeRecommendationRequest(BaseModel):
    """Модель запроса рекомендаций на основе кода."""

    code: str = Field(
        ..., description="Код для анализа", max_length=100000
    )  # Limit length
    configName: Optional[str] = Field(
        None, description="Название конфигурации (опционально)", max_length=50
    )


# ==================== API ENDPOINTS ====================


@router.get(
    "/configurations",
    tags=["Knowledge Base"],
    summary="Список поддерживаемых конфигураций",
    description="Получение списка всех поддерживаемых типовых конфигураций 1С",
)
async def get_configurations() -> Dict[str, Any]:
    """Получает список поддерживаемых конфигураций.

    Returns:
        Dict[str, Any]: Словарь со списком конфигураций и их общим количеством.
    """
    kb = get_knowledge_base()

    configurations = []
    for config_key in kb.SUPPORTED_CONFIGURATIONS:
        info = kb.get_configuration_info(config_key)
        if info:
            configurations.append(
                {
                    "id": config_key,
                    "name": info.get("name", config_key),
                    "modules_count": len(info.get("modules", [])),
                    "best_practices_count": len(info.get("best_practices", [])),
                    "patterns_count": len(info.get("common_patterns", [])),
                }
            )

    return {"configurations": configurations, "total": len(configurations)}


@router.get(
    "/configurations/{config_name}",
    tags=["Knowledge Base"],
    summary="Информация о конфигурации",
    description="Получение подробной информации о конкретной конфигурации",
)
async def get_configuration_info(config_name: str) -> Dict[str, Any]:
    """Получает информацию о конфигурации с валидацией входных данных.

    Args:
        config_name: Название конфигурации.

    Returns:
        Dict[str, Any]: Информация о конфигурации.

    Raises:
        HTTPException: Если имя конфигурации некорректно или конфигурация не найдена.
    """
    # Input validation and sanitization (best practice)
    sanitized_name = config_name.strip().lower()[:50]  # Limit length and normalize
    if not sanitized_name:
        raise HTTPException(
            status_code=400, detail="Configuration name cannot be empty"
        )

    # Prevent path traversal and dangerous characters
    if ".." in sanitized_name or "/" in sanitized_name or "\\" in sanitized_name:
        raise HTTPException(status_code=400, detail="Invalid configuration name")

    kb = get_knowledge_base()
    info = kb.get_configuration_info(sanitized_name)

    if not info:
        raise HTTPException(
            status_code=404, detail=f"Конфигурация {sanitized_name} не найдена"
        )

    return info


@router.post(
    "/recommendations",
    tags=["Knowledge Base"],
    summary="Рекомендации на основе кода",
    description="Получение рекомендаций на основе анализа кода и базы знаний",
)
async def get_recommendations(request: CodeRecommendationRequest) -> Dict[str, Any]:
    """Получает рекомендации на основе кода с валидацией входных данных.

    Args:
        request: Объект запроса с кодом и опциональным именем конфигурации.

    Returns:
        Dict[str, Any]: Список рекомендаций.

    Raises:
        HTTPException: Если код пустой, слишком длинный или имя конфигурации некорректно.
    """
    try:
        # Input validation and sanitization (best practice)
        code = request.code.strip()
        if not code:
            raise HTTPException(status_code=400, detail="Code cannot be empty")

        # Limit code length (prevent DoS)
        max_code_length = 100000  # 100KB max
        if len(code) > max_code_length:
            raise HTTPException(
                status_code=400,
                detail=f"Code too long. Maximum length: {max_code_length} characters",
            )

        # Sanitize config name if provided
        config_name = None
        if request.configName:
            config_name = request.configName.strip().lower()[:50]
            # Prevent path traversal
            if ".." in config_name or "/" in config_name or "\\" in config_name:
                raise HTTPException(
                    status_code=400, detail="Invalid configuration name"
                )

        kb = get_knowledge_base()
        recommendations = kb.get_recommendations(code=code, config_name=config_name)

        return {"recommendations": recommendations, "total": len(recommendations)}

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(
            "Unexpected error getting recommendations",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "code_length": len(request.code) if hasattr(request, "code") else 0,
                "config_name": (
                    request.configName if hasattr(request, "configName") else None
                ),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="An error occurred while getting recommendations"
        )


@router.post(
    "/patterns/search",
    tags=["Knowledge Base"],
    summary="Поиск паттернов",
    description="Поиск паттернов в базе знаний",
)
async def search_patterns(request: PatternSearchRequest) -> Dict[str, Any]:
    """Ищет паттерны в базе знаний с валидацией входных данных.

    Args:
        request: Объект запроса с параметрами поиска.

    Returns:
        Dict[str, Any]: Список найденных паттернов.

    Raises:
        HTTPException: Если имя конфигурации некорректно.
    """
    try:
        # Input validation and sanitization (best practice)
        config_name = None
        if request.configName:
            config_name = request.configName.strip().lower()[:50]
            # Prevent path traversal
            if ".." in config_name or "/" in config_name or "\\" in config_name:
                raise HTTPException(
                    status_code=400, detail="Invalid configuration name"
                )

        pattern_type = None
        if request.patternType:
            pattern_type = request.patternType.strip()[:100]  # Limit length

        query = None
        if request.query:
            query = request.query.strip()[:500]  # Limit length

        kb = get_knowledge_base()
        patterns = kb.search_patterns(
            config_name=config_name, pattern_type=pattern_type, query=query
        )

        return {"patterns": patterns, "total": len(patterns)}

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(
            "Unexpected error searching patterns",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "config_name": (
                    request.configName if hasattr(request, "configName") else None
                ),
                "pattern_type": (
                    request.patternType if hasattr(request, "patternType") else None
                ),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="An error occurred while searching patterns"
        )


@router.post(
    "/modules",
    tags=["Knowledge Base"],
    summary="Добавление документации модуля",
    description="Добавление документации модуля в базу знаний",
)
async def add_module_documentation(
    request: ModuleDocumentationRequest,
) -> Dict[str, Any]:
    """Добавляет документацию модуля с валидацией входных данных.

    Args:
        request: Объект запроса с данными модуля.

    Returns:
        Dict[str, Any]: Результат операции.

    Raises:
        HTTPException: Если данные некорректны или не удалось добавить документацию.
    """
    try:
        # Input validation and sanitization (best practice)
        config_name = request.configName.strip().lower()[:50]
        if not config_name:
            raise HTTPException(
                status_code=400, detail="Configuration name cannot be empty"
            )

        # Prevent path traversal
        if ".." in config_name or "/" in config_name or "\\" in config_name:
            raise HTTPException(status_code=400, detail="Invalid configuration name")

        module_name = request.moduleName.strip()[:200]  # Limit length
        if not module_name:
            raise HTTPException(status_code=400, detail="Module name cannot be empty")

        kb = get_knowledge_base()
        success = kb.add_module_documentation(
            config_name=config_name,
            module_name=module_name,
            documentation=request.documentation,
        )

        if not success:
            raise HTTPException(
                status_code=400, detail="Не удалось добавить документацию модуля"
            )

        return {
            "success": True,
            "message": f"Документация модуля {module_name} добавлена",
        }

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(
            "Unexpected error adding module documentation",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "config_name": (
                    request.configName if hasattr(request, "configName") else None
                ),
                "module_name": (
                    request.moduleName if hasattr(request, "moduleName") else None
                ),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An error occurred while adding module documentation",
        )


@router.post(
    "/best-practices",
    tags=["Knowledge Base"],
    summary="Добавление best practice",
    description="Добавление best practice в базу знаний",
)
async def add_best_practice(request: BestPracticeRequest) -> Dict[str, Any]:
    """Добавляет лучшую практику в базу знаний.

    Args:
        request: Объект запроса с данными практики.

    Returns:
        Dict[str, Any]: Результат операции.

    Raises:
        HTTPException: Если не удалось добавить практику.
    """
    try:
        kb = get_knowledge_base()
        success = kb.add_best_practice(
            config_name=request.configName,
            category=request.category,
            practice=request.practice,
        )

        if not success:
            raise HTTPException(
                status_code=400, detail="Не удалось добавить best practice"
            )

        return {"success": True, "message": "Best practice добавлена"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Ошибка добавления best practice",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "config_name": (
                    request.configName if hasattr(request, "configName") else None
                ),
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Ошибка добавления best practice")


@router.post(
    "/load-from-directory",
    tags=["Knowledge Base"],
    summary="Загрузка конфигураций из директории",
    description="Загрузка конфигураций 1С из указанной директории",
)
async def load_from_directory(directory_path: str) -> Dict[str, Any]:
    """Загружает конфигурации из указанной директории.

    Args:
        directory_path: Путь к директории с конфигурациями.

    Returns:
        Dict[str, Any]: Результат загрузки.

    Raises:
        HTTPException: Если произошла ошибка при загрузке.
    """
    try:
        kb = get_knowledge_base()
        loaded_count = kb.load_from_directory(directory_path)

        return {
            "success": True,
            "loaded_configurations": loaded_count,
            "message": f"Загружено конфигураций: {loaded_count}",
        }

    except Exception as e:
        logger.error(
            "Ошибка загрузки из директории",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "directory_path": (
                    directory_path if "directory_path" in locals() else None
                ),
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Ошибка загрузки из директории")


@router.get(
    "/health", tags=["Knowledge Base"], summary="Проверка состояния базы знаний"
)
async def health_check() -> Dict[str, Any]:
    """Проверяет доступность и состояние базы знаний.

    Returns:
        Dict[str, Any]: Статус здоровья и статистика.
    """
    kb = get_knowledge_base()

    total_configs = 0
    total_modules = 0
    total_practices = 0
    total_patterns = 0

    for config_key in kb.SUPPORTED_CONFIGURATIONS:
        info = kb.get_configuration_info(config_key)
        if info:
            total_configs += 1
            total_modules += len(info.get("modules", []))
            total_practices += len(info.get("best_practices", []))
            total_patterns += len(info.get("common_patterns", []))

    return {
        "status": "healthy",
        "service": "knowledge-base",
        "version": "1.0.0",
        "statistics": {
            "total_configurations": total_configs,
            "total_modules": total_modules,
            "total_best_practices": total_practices,
            "total_patterns": total_patterns,
        },
    }
